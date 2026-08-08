from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from why import store
from why.bootstrap import ensure_ready
from why.cli import app
from why.config import load_config, write_config

runner = CliRunner()


def test_follow_start_status_stop(why_home: Path) -> None:
    result = runner.invoke(
        app,
        ["follow", "start", "--title", "Install Postgres", "--project", "demo"],
    )
    assert result.exit_code == 0
    assert "Recording session" in result.stdout

    status = runner.invoke(app, ["follow", "status"])
    assert status.exit_code == 0
    assert "Install Postgres" in status.stdout

    stop = runner.invoke(app, ["follow", "stop"])
    assert stop.exit_code == 0
    assert "why sessions show" in stop.stdout
    assert "why sessions summarize" in stop.stdout


def test_record_hidden_command_adds_journal_and_active_session(why_home: Path) -> None:
    runner.invoke(app, ["follow", "start", "--title", "Task"])

    result = runner.invoke(
        app,
        [
            "_record",
            "--cmd",
            "brew install postgresql@16",
            "--cwd",
            "/tmp/demo",
            "--code",
            "0",
            "--shell",
            "zsh",
        ],
    )

    assert result.exit_code == 0
    db = ensure_ready()
    journal = store.list_recent_command_journal(db, limit=1)
    assert journal[0].command == "brew install postgresql@16"
    active = store.get_active_task_session(db)
    assert active is not None
    commands = store.list_task_session_commands(db, active.id)
    assert [cmd.command for cmd in commands] == ["brew install postgresql@16"]


def test_recall_creates_closed_session_from_journal(why_home: Path) -> None:
    db = ensure_ready()
    for command in ("one", "two", "three"):
        store.add_command_journal_entry(
            db,
            command=command,
            cwd="/tmp/demo",
            shell="zsh",
            exit_code=0,
        )

    result = runner.invoke(app, ["recall", "--last", "2", "--title", "Recall"])

    assert result.exit_code == 0
    sessions = store.list_task_sessions(db, limit=10)
    assert sessions[0].source == "recall"
    assert sessions[0].status == "closed"
    commands = store.list_task_session_commands(db, sessions[0].id)
    assert [cmd.command for cmd in commands] == ["two", "three"]


def test_recall_interactive_selects_subset(why_home: Path) -> None:
    db = ensure_ready()
    for command in ("one", "two", "three"):
        store.add_command_journal_entry(
            db,
            command=command,
            cwd="/tmp/demo",
            shell="zsh",
            exit_code=0,
        )

    result = runner.invoke(app, ["recall", "--last", "3", "--interactive"], input="1,3\n")

    assert result.exit_code == 0
    session = store.list_task_sessions(db, limit=1)[0]
    commands = store.list_task_session_commands(db, session.id)
    assert [cmd.command for cmd in commands] == ["one", "three"]


def test_sessions_show_displays_transcript(why_home: Path) -> None:
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
        title="Task",
        project=None,
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

    result = runner.invoke(app, ["sessions", "show", str(session.id)])

    assert result.exit_code == 0
    assert "brew install postgresql@16" in result.stdout
    assert "/tmp/demo" in result.stdout
    assert "Summary:" in result.stdout


def test_sessions_ignore_llm_sets_ignored_status(why_home: Path) -> None:
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
        title="Task",
        project=None,
        shell="zsh",
        cwd_start="/tmp/demo",
    )

    result = runner.invoke(app, ["sessions", "ignore-llm", str(session.id)])

    assert result.exit_code == 0
    updated = store.get_task_session(db, session.id)
    assert updated is not None
    assert updated.summary_status == "ignored"


def test_sessions_summarize_print_payload_does_not_call_network(why_home: Path) -> None:
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
        title="Task",
        project=None,
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

    result = runner.invoke(app, ["sessions", "summarize", str(session.id), "--print-payload"])

    assert result.exit_code == 0
    assert '"task_session"' in result.stdout
    assert "brew install postgresql@16" in result.stdout


def test_record_exits_zero_when_config_is_corrupt(why_home: Path) -> None:
    """`why _record` runs on every shell prompt and must never fail the terminal.

    CLAUDE.md: "Hook failed" should log to ~/.why/hook.log and exit 0. Regression
    test: record_cmd had no try/except, unlike run_hook, so a corrupt config.toml
    produced rc=1 plus a ~4KB Rich traceback on every prompt draw.
    """
    ensure_ready()
    (why_home / "config.toml").write_text("this is not valid toml {{{\n")

    result = runner.invoke(
        app,
        ["_record", "--cmd", "echo hi", "--cwd", "/tmp", "--code", "0", "--shell", "zsh"],
    )

    assert result.exit_code == 0, f"_record must exit 0; got {result.exit_code}"
    assert "Traceback" not in result.stdout


def test_recall_refuses_when_journal_is_empty(why_home: Path) -> None:
    """`why recall` on an empty journal must not create a zero-command session.

    The --interactive branch already refuses; the default path created a closed
    session with 0 commands and then advertised `why sessions show/summarize` for it.
    """
    ensure_ready()

    result = runner.invoke(app, ["recall"])

    assert result.exit_code != 0
    assert "no recent commands" in result.stdout.lower()

    db = ensure_ready()
    assert store.list_task_sessions(db) == [], "an empty recall session was created"


def test_summarize_reports_llm_failure_cleanly(why_home: Path, monkeypatch) -> None:
    """An LLM failure must not dump a traceback, and must mark the session failed.

    The web path set summary_status='failed'; the CLI left it at 'none' and raised.
    """
    import why.llm as llm_mod

    db = ensure_ready()
    session = _seed_closed_session(db)
    cfg = load_config()
    cfg["llm"].update({"enabled": True, "confirm_before_send": "never"})
    write_config(cfg)

    def boom(**kw):
        raise RuntimeError("LLM request failed: connection refused")

    monkeypatch.setattr(llm_mod, "summarize_openai_compatible", boom)

    result = runner.invoke(app, ["sessions", "summarize", str(session.id)])

    assert result.exit_code == 1
    assert "Traceback" not in result.stdout
    assert "connection refused" in result.stdout
    refreshed = store.get_task_session(db, session.id)
    assert refreshed is not None
    assert refreshed.summary_status == "failed"


def _seed_closed_session(db):
    user = store.get_solo_user(db)
    device = store.get_solo_device(db)
    assert user is not None and device is not None
    s = store.create_task_session(
        db, user_id=user.id, device_id=device.id, source="follow", status="closed",
        title="t", project=None, shell="zsh", cwd_start="/tmp",
    )
    store.append_task_session_command(
        db, s.id, command="brew install rg", cwd="/tmp", exit_code=0,
        started_at="2026-08-08T00:00:00+00:00",
    )
    return s


def test_store_summaries_false_does_not_persist(why_home: Path, monkeypatch) -> None:
    """store_summaries is documented and written into every config, but was read
    nowhere: setting it false still stored every summary.
    """
    import why.llm as llm_mod

    db = ensure_ready()
    session = _seed_closed_session(db)
    cfg = load_config()
    cfg["llm"].update(
        {"enabled": True, "confirm_before_send": "never", "store_summaries": False}
    )
    write_config(cfg)
    monkeypatch.setattr(llm_mod, "summarize_openai_compatible", lambda **kw: "# Recap\n")

    result = runner.invoke(app, ["sessions", "summarize", str(session.id)])

    assert result.exit_code == 0
    assert "# Recap" in result.stdout, "summary should still be shown"
    assert store.list_task_session_summaries(db, session.id) == [], (
        "summary was stored despite store_summaries = false"
    )
    refreshed = store.get_task_session(db, session.id)
    assert refreshed is not None
    assert refreshed.summary_status == "complete", (
        "a successful summarize must mark the session complete even when the text "
        "is not stored, or it reappears in 'needs summary' views forever"
    )


def test_llm_test_actually_contacts_the_endpoint(why_home: Path) -> None:
    """`why llm test` printed config and exited 0 even against a dead endpoint."""
    ensure_ready()
    cfg = load_config()
    cfg["llm"].update(
        {"enabled": True, "base_url": "http://127.0.0.1:1/v1", "timeout_seconds": 2}
    )
    write_config(cfg)

    result = runner.invoke(app, ["llm", "test"])

    assert result.exit_code != 0, "llm test passed against a connection-refused endpoint"


def _run_cli(args, why_home: Path):
    """Run the real CLI with stdin closed.

    CliRunner(input="") is NOT a faithful non-TTY harness -- it reports no abort
    where a real `< /dev/null` pipe does. These must go through a subprocess.
    """
    import os
    import subprocess

    return subprocess.run(
        ["uv", "run", "why", *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        env={**os.environ, "WHY_HOME": str(why_home)},
    )


def test_llm_configure_has_non_tty_fallback(why_home: Path) -> None:
    """CLAUDE.md: every interactive prompt needs a non-TTY fallback."""
    ensure_ready()

    result = _run_cli(["llm", "configure"], why_home)

    assert "Aborted" not in (result.stdout + result.stderr)


def test_recall_interactive_has_non_tty_fallback(why_home: Path) -> None:
    db = ensure_ready()
    store.add_command_journal_entry(
        db, command="echo one", cwd="/tmp", shell="zsh", exit_code=0
    )

    result = _run_cli(["recall", "--interactive"], why_home)

    assert "Aborted" not in (result.stdout + result.stderr)


def test_sessions_unignore_llm_exists(why_home: Path) -> None:
    """The web UI has an un-ignore button; a CLI-only user had no way back."""
    db = ensure_ready()
    session = _seed_closed_session(db)
    runner.invoke(app, ["sessions", "ignore-llm", str(session.id)])

    result = runner.invoke(app, ["sessions", "unignore-llm", str(session.id)])

    assert result.exit_code == 0
    refreshed = store.get_task_session(db, session.id)
    assert refreshed is not None and refreshed.summary_status == "none"


def test_sessions_delete_soft_deletes(why_home: Path) -> None:
    db = ensure_ready()
    session = _seed_closed_session(db)

    result = runner.invoke(app, ["sessions", "delete", str(session.id)])

    assert result.exit_code == 0
    assert store.get_task_session(db, session.id) is None
    # soft by default: the row survives as a sync tombstone
    assert store.list_task_session_commands(db, session.id) != []


def test_sessions_delete_purge_removes_everything(why_home: Path) -> None:
    db = ensure_ready()
    session = _seed_closed_session(db)

    result = runner.invoke(app, ["sessions", "delete", str(session.id), "--purge"])

    assert result.exit_code == 0
    assert store.get_task_session(db, session.id) is None
    assert store.list_task_session_commands(db, session.id) == []


def test_sessions_delete_reports_unknown_id(why_home: Path) -> None:
    ensure_ready()

    result = runner.invoke(app, ["sessions", "delete", "999"])

    assert result.exit_code == 1
    assert "999" in result.stdout
