from __future__ import annotations

from pathlib import Path

import pytest

from why import llm, store
from why.bootstrap import ensure_ready
from why.llm import build_task_payload, build_user_prompt, normalized_payload_hash


def _session_with_commands(db: Path) -> tuple[store.TaskSession, list[store.TaskSessionCommand]]:
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
    first = store.append_task_session_command(
        db,
        session.id,
        command="brew install postgresql@16",
        cwd="/tmp/demo",
        exit_code=0,
        started_at="2026-07-08T10:00:00+00:00",
    )
    second = store.append_task_session_command(
        db,
        session.id,
        command="aws secret-project deploy",
        cwd="/tmp/demo",
        exit_code=0,
        started_at="2026-07-08T10:01:00+00:00",
    )
    return session, [first, second]


def test_payload_omits_llm_ignored_commands(why_home: Path) -> None:
    db = ensure_ready()
    session, commands = _session_with_commands(db)

    payload = build_task_payload(
        session,
        commands,
        [],
        max_commands=10,
        llm_ignore_patterns=("secret-project",),
    )

    assert payload["commands"] == [
        {
            "position": 0,
            "command": "brew install postgresql@16",
            "cwd": "/tmp/demo",
            "exit_code": 0,
            "started_at": "2026-07-08T10:00:00+00:00",
            "ended_at": None,
            "matched_install_id": None,
        }
    ]
    assert payload["omissions"] == {
        "truncated_commands": 0,
        "truncated_from": "oldest",
        "llm_ignored_commands": 1,
    }


def test_payload_hash_is_stable_for_key_order() -> None:
    assert normalized_payload_hash({"b": 1, "a": 2}) == normalized_payload_hash(
        {"a": 2, "b": 1}
    )


def test_user_prompt_contains_payload_json_and_required_sections(why_home: Path) -> None:
    db = ensure_ready()
    session, commands = _session_with_commands(db)
    payload = build_task_payload(
        session,
        commands[:1],
        [],
        max_commands=10,
        llm_ignore_patterns=(),
    )

    prompt = build_user_prompt(payload)

    assert "Session JSON" in prompt
    assert "## Clean steps" in prompt
    assert "## Gotchas" in prompt
    assert "brew install postgresql@16" in prompt


# --- error paths -----------------------------------------------------------


def _call(**over):
    kw = dict(
        base_url="http://localhost:11434/v1",
        api_key=None,
        model="m",
        system_prompt="s",
        user_prompt="u",
        timeout_seconds=1,
    )
    kw.update(over)
    return llm.summarize_openai_compatible(**kw)


def test_timeout_becomes_runtime_error(monkeypatch) -> None:
    """A urlopen timeout raises TimeoutError, which is NOT a URLError subclass.

    Real scenario: local Ollama is loading a large model and exceeds timeout_seconds.
    """

    def boom(*a, **k):
        raise TimeoutError("timed out")

    monkeypatch.setattr(llm.urllib.request, "urlopen", boom)
    with pytest.raises(RuntimeError):
        _call()


def test_non_json_body_becomes_runtime_error(monkeypatch) -> None:
    """A proxy or gateway returning an HTML login page with status 200."""

    class FakeResp:
        def read(self):
            return b"<html>login</html>"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda *a, **k: FakeResp())
    with pytest.raises(RuntimeError):
        _call()


def test_no_hardcoded_api_key_env_fallback(monkeypatch) -> None:
    """A stale WHY_LLM_API_KEY must not be sent when the configured var is unset.

    Otherwise credential A ships to provider B and surfaces as a confusing 401.
    """
    monkeypatch.setenv("WHY_LLM_API_KEY", "sk-STALE-LEFTOVER")
    seen: dict = {}

    class FakeResp:
        def read(self):
            return b'{"choices":[{"message":{"content":"ok"}}]}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def capture(req, *a, **k):
        seen.update(req.headers)
        return FakeResp()

    monkeypatch.setattr(llm.urllib.request, "urlopen", capture)
    _call(api_key=None)

    assert not any("authorization" in k.lower() for k in seen), (
        f"stale env key was sent: {seen}"
    )


def test_truncation_keeps_the_most_recent_commands(why_home: Path) -> None:
    """The prompt asks for "the final useful commands", so keeping the oldest N
    deletes exactly the material the recap is supposed to describe.
    """
    db = ensure_ready()
    session, commands = _session_with_commands(db)
    payload = build_task_payload(
        session, commands, [], max_commands=1, llm_ignore_patterns=()
    )
    kept = [c["command"] for c in payload["commands"]]
    expected = [c.command for c in commands][-1:]

    assert kept == expected, f"kept oldest instead of newest: {kept} != {expected}"


def test_truncation_records_which_end_was_dropped(why_home: Path) -> None:
    db = ensure_ready()
    session, commands = _session_with_commands(db)
    payload = build_task_payload(
        session, commands, [], max_commands=1, llm_ignore_patterns=()
    )
    om = payload["omissions"]

    assert om["truncated_commands"] == len(commands) - 1
    assert om["truncated_from"] == "oldest", "model cannot tell which end was cut"


def test_invalid_ignore_regex_raises_clean_error(why_home: Path) -> None:
    """One typo in ~/.why/llm-ignore.toml must not produce a raw re.error."""
    db = ensure_ready()
    session, commands = _session_with_commands(db)

    with pytest.raises(ValueError, match="llm-ignore"):
        build_task_payload(
            session, commands, [], max_commands=10, llm_ignore_patterns=("aws (",)
        )


def test_max_commands_is_clamped_to_at_least_one(why_home: Path) -> None:
    """A negative max_input_commands would behead the newest commands via [: -n]."""
    db = ensure_ready()
    session, commands = _session_with_commands(db)
    payload = build_task_payload(
        session, commands, [], max_commands=-3, llm_ignore_patterns=()
    )

    assert len(payload["commands"]) >= 1
    assert payload["omissions"]["truncated_commands"] >= 0
