from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from why import store
from why.bootstrap import ensure_ready
from why.config import load_config
from why.web.app import create_app


def _client(why_home: Path) -> TestClient:
    ensure_ready()
    c = TestClient(create_app())
    c.get("/sessions")
    return c


def _seed_session(why_home: Path) -> int:
    db = ensure_ready()
    user = store.get_solo_user(db)
    device = store.get_solo_device(db)
    assert user is not None
    assert device is not None
    session = store.create_task_session(
        db,
        user_id=user.id,
        device_id=device.id,
        source="follow",
        status="closed",
        title="Install Postgres",
        project="demo",
        shell="zsh",
        cwd_start="/tmp/demo",
    )
    store.append_task_session_command(
        db,
        session.id,
        command="brew install postgresql@16",
        cwd="/tmp/demo",
        exit_code=0,
        started_at=session.started_at,
    )
    return session.id


def test_sessions_page_lists_sessions(why_home: Path) -> None:
    _seed_session(why_home)
    c = _client(why_home)

    r = c.get("/sessions")

    assert r.status_code == 200
    assert "Install Postgres" in r.text
    assert "follow" in r.text
    assert "none" in r.text


def test_session_detail_shows_transcript(why_home: Path) -> None:
    session_id = _seed_session(why_home)
    db = ensure_ready()
    store.save_task_session_summary(
        db,
        session_id,
        provider="openai-compatible",
        model="llama3.1",
        endpoint="http://localhost:11434/v1",
        prompt_version=1,
        input_hash="abc",
        summary_markdown="# Install Postgres\n",
    )
    c = _client(why_home)

    r = c.get(f"/sessions/{session_id}")

    assert r.status_code == 200
    assert "brew install postgresql@16" in r.text
    assert "/tmp/demo" in r.text
    assert "# Install Postgres" in r.text


def test_ignore_llm_action_sets_ignored(why_home: Path) -> None:
    session_id = _seed_session(why_home)
    c = _client(why_home)

    r = c.post(
        f"/sessions/{session_id}/ignore-llm",
        data={"csrf_token": c.cookies.get("why_csrf", "")},
        follow_redirects=False,
    )

    assert r.status_code == 303
    db = ensure_ready()
    session = store.get_task_session(db, session_id)
    assert session is not None
    assert session.summary_status == "ignored"


def test_llm_settings_round_trip(why_home: Path) -> None:
    c = _client(why_home)

    r = c.post(
        "/settings/llm",
        data={
            "csrf_token": c.cookies.get("why_csrf", ""),
            "enabled": "1",
            "provider": "openai-compatible",
            "base_url": "http://localhost:11434/v1",
            "model": "llama3.2",
            "api_key_env": "WHY_TEST_KEY",
            "confirm_before_send": "always",
            "max_input_commands": "50",
        },
        follow_redirects=False,
    )

    assert r.status_code == 303
    cfg = load_config()
    assert cfg["llm"]["enabled"] is True
    assert cfg["llm"]["model"] == "llama3.2"
    assert cfg["llm"]["api_key_env"] == "WHY_TEST_KEY"
    assert cfg["llm"]["confirm_before_send"] == "always"
    assert cfg["llm"]["max_input_commands"] == 50


def _enable_llm(confirm: str, base_url: str = "https://api.openai.com/v1") -> None:
    from why.config import write_config

    cfg = load_config()
    cfg["llm"].update(
        {"enabled": True, "confirm_before_send": confirm, "base_url": base_url}
    )
    write_config(cfg)


def test_web_summarize_honors_confirm_before_send(why_home: Path, monkeypatch) -> None:
    """The web route must respect confirm_before_send, exactly as the CLI does.

    Regression test: the CLI gated sending behind _requires_confirmation but the
    web route had no equivalent, so one click sent a full terminal transcript to a
    remote endpoint the user had configured to always confirm.
    """
    import why.web.routes.sessions as routes

    sent: list[str] = []
    monkeypatch.setattr(
        routes, "summarize_openai_compatible", lambda **kw: sent.append(kw["base_url"]) or "x"
    )

    client = _client(why_home)
    session_id = _seed_session(why_home)
    _enable_llm("always")

    resp = client.post(
        f"/sessions/{session_id}/summarize",
        data={"csrf_token": client.cookies.get("why_csrf", "")},
        follow_redirects=False,
    )

    assert sent == [], "web route sent the transcript without confirmation"
    assert resp.status_code == 303
    assert "confirm" in resp.headers["location"]


def test_web_summarize_sends_when_confirmed(why_home: Path, monkeypatch) -> None:
    """An explicit confirmation carries the send through."""
    import why.web.routes.sessions as routes

    sent: list[str] = []
    monkeypatch.setattr(
        routes,
        "summarize_openai_compatible",
        lambda **kw: (sent.append(kw["base_url"]), "# Recap\n")[1],
    )

    client = _client(why_home)
    session_id = _seed_session(why_home)
    _enable_llm("always")

    client.post(
        f"/sessions/{session_id}/summarize",
        data={"confirmed": "1", "csrf_token": client.cookies.get("why_csrf", "")},
        follow_redirects=False,
    )

    assert sent == ["https://api.openai.com/v1"]


def test_web_summarize_local_endpoint_needs_no_confirmation(why_home: Path, monkeypatch) -> None:
    """policy='remote' must not gate a localhost endpoint - matching the CLI."""
    import why.web.routes.sessions as routes

    sent: list[str] = []
    monkeypatch.setattr(
        routes,
        "summarize_openai_compatible",
        lambda **kw: (sent.append(kw["base_url"]), "# Recap\n")[1],
    )

    client = _client(why_home)
    session_id = _seed_session(why_home)
    _enable_llm("remote", base_url="http://localhost:11434/v1")

    client.post(
        f"/sessions/{session_id}/summarize",
        data={"csrf_token": client.cookies.get("why_csrf", "")},
        follow_redirects=False,
    )

    assert sent == ["http://localhost:11434/v1"]


def test_confirm_page_shows_endpoint_and_command_count(why_home: Path) -> None:
    """The confirmation gate must tell the user exactly what leaves the machine."""
    client = _client(why_home)
    session_id = _seed_session(why_home)
    _enable_llm("always")

    r = client.get(f"/sessions/{session_id}?confirm=1")

    assert r.status_code == 200
    assert "Send this transcript off this machine?" in r.text
    assert "https://api.openai.com/v1" in r.text
    assert "1 command will be sent" in r.text


def test_session_detail_has_no_confirm_panel_by_default(why_home: Path) -> None:
    client = _client(why_home)
    session_id = _seed_session(why_home)

    r = client.get(f"/sessions/{session_id}")

    assert "Send this transcript off this machine?" not in r.text


def test_bad_ignore_regex_does_not_500(why_home: Path) -> None:
    """A typo in llm-ignore.toml must not be an HTTP 500.

    build_task_payload sat outside the guarded region, so re.error escaped the route.
    """
    client = _client(why_home)
    session_id = _seed_session(why_home)
    _enable_llm("never")
    (why_home / "llm-ignore.toml").write_text('patterns = ["aws ("]\n')

    r = client.post(
        f"/sessions/{session_id}/summarize",
        data={"csrf_token": client.cookies.get("why_csrf", "")},
        follow_redirects=False,
    )

    assert r.status_code != 500, "bad user regex produced a server error"


def test_web_summarize_failure_is_logged(why_home: Path, monkeypatch) -> None:
    """A blanket contextlib.suppress(Exception) left no trace of why it failed."""
    import why.web.routes.sessions as routes

    def boom(**kw):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(routes, "summarize_openai_compatible", boom)

    client = _client(why_home)
    session_id = _seed_session(why_home)
    _enable_llm("never")

    client.post(
        f"/sessions/{session_id}/summarize",
        data={"csrf_token": client.cookies.get("why_csrf", "")},
        follow_redirects=False,
    )

    log = (why_home / "hook.log")
    assert log.exists() and "connection refused" in log.read_text(), (
        "summarize failure left no diagnostic trace"
    )


def test_settings_clamps_negative_max_input_commands(why_home: Path) -> None:
    """min="1" in the template is client-side only; a crafted POST bypassed it."""
    client = _client(why_home)

    client.post(
        "/settings/llm",
        data={
            "enabled": "1",
            "max_input_commands": "-3",
            "csrf_token": client.cookies.get("why_csrf", ""),
        },
        follow_redirects=False,
    )

    assert load_config()["llm"]["max_input_commands"] >= 1


def test_sessions_empty_state_is_about_sessions(why_home: Path) -> None:
    """sessions.html passed title=/body= but the partial reads line=, so Jinja
    silently ignored both and the default "No installs yet" copy rendered.
    """
    client = _client(why_home)

    r = client.get("/sessions")

    assert "No sessions yet" in r.text
    assert "No installs yet" not in r.text
    assert "&lt;code" not in r.text, "escaped HTML leaked into the empty state"


def test_footer_privacy_claim_reflects_llm_state(why_home: Path) -> None:
    """The footer asserted "no network" on every page, including /settings/llm."""
    client = _client(why_home)

    off = client.get("/sessions")
    assert "no network" in off.text

    _enable_llm("always")
    on = client.get("/sessions")
    assert "no network" not in on.text, "footer still claims no network with LLM enabled"


def test_web_summarize_honors_store_summaries(why_home: Path, monkeypatch) -> None:
    import why.web.routes.sessions as routes

    monkeypatch.setattr(routes, "summarize_openai_compatible", lambda **kw: "# Recap\n")
    client = _client(why_home)
    session_id = _seed_session(why_home)
    cfg = load_config()
    cfg["llm"].update(
        {"enabled": True, "confirm_before_send": "never", "store_summaries": False}
    )
    from why.config import write_config

    write_config(cfg)

    client.post(
        f"/sessions/{session_id}/summarize",
        data={"csrf_token": client.cookies.get("why_csrf", "")},
        follow_redirects=False,
    )

    db = ensure_ready()
    assert store.list_task_session_summaries(db, session_id) == []


def test_web_delete_session(why_home: Path) -> None:
    client = _client(why_home)
    session_id = _seed_session(why_home)

    r = client.post(
        f"/sessions/{session_id}/delete",
        data={"csrf_token": client.cookies.get("why_csrf", "")},
        follow_redirects=False,
    )

    assert r.status_code == 303
    db = ensure_ready()
    assert store.get_task_session(db, session_id) is None


def test_session_detail_offers_delete_and_purge(why_home: Path) -> None:
    """Purge is irreversible, so the UI must distinguish it from a plain delete."""
    client = _client(why_home)
    session_id = _seed_session(why_home)

    r = client.get(f"/sessions/{session_id}")

    assert f"/sessions/{session_id}/delete" in r.text
    assert "Erase transcript" in r.text
    assert "confirm" in r.text.lower(), "irreversible purge offered with no confirmation"
