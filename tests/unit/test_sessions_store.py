from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from why import store
from why.bootstrap import ensure_ready
from why.sessions import (
    create_recall_session,
    parse_selection,
    record_command_event,
    start_follow_session,
)


def _ids(db: Path) -> tuple[str, str]:
    user = store.get_solo_user(db)
    device = store.get_solo_device(db)
    assert user is not None
    assert device is not None
    return user.id, device.id


def _create_session(db: Path, *, status: str = "active") -> store.TaskSession:
    user_id, device_id = _ids(db)
    return store.create_task_session(
        db,
        user_id=user_id,
        device_id=device_id,
        source="follow",
        status=status,
        title="Install Postgres",
        project="demo",
        shell="zsh",
        cwd_start="/tmp/demo",
    )


def test_task_session_lifecycle(why_home: Path) -> None:
    db = ensure_ready()
    session = _create_session(db)

    active = store.get_active_task_session(db)
    assert active is not None
    assert active.id == session.id
    assert active.status == "active"

    closed = store.close_task_session(db, session.id, cwd_end="/tmp/demo")
    assert closed.status == "closed"
    assert closed.ended_at is not None
    assert closed.cwd_end == "/tmp/demo"
    assert store.get_active_task_session(db) is None

    cancelled_session = _create_session(db)
    cancelled = store.cancel_task_session(db, cancelled_session.id)
    assert cancelled.status == "cancelled"
    assert cancelled.ended_at is not None


def test_append_commands_preserves_positions(why_home: Path) -> None:
    db = ensure_ready()
    session = _create_session(db)

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
        command="brew services start postgresql@16",
        cwd="/tmp/demo",
        exit_code=0,
        started_at="2026-07-08T10:01:00+00:00",
    )

    assert first.position == 0
    assert second.position == 1
    commands = store.list_task_session_commands(db, session.id)
    assert [cmd.command for cmd in commands] == [
        "brew install postgresql@16",
        "brew services start postgresql@16",
    ]


def test_summary_updates_summary_status(why_home: Path) -> None:
    db = ensure_ready()
    session = _create_session(db, status="closed")

    summary = store.save_task_session_summary(
        db,
        session.id,
        provider="openai-compatible",
        model="llama3.1",
        endpoint="http://localhost:11434/v1",
        prompt_version=1,
        input_hash="abc123",
        summary_markdown="# Install Postgres\n",
    )

    assert summary.summary_markdown == "# Install Postgres\n"
    updated = store.get_task_session(db, session.id)
    assert updated is not None
    assert updated.summary_status == "complete"
    summaries = store.list_task_session_summaries(db, session.id)
    assert [s.id for s in summaries] == [summary.id]


def test_ignore_llm_sets_summary_status_ignored(why_home: Path) -> None:
    db = ensure_ready()
    session = _create_session(db, status="closed")

    ignored = store.set_task_session_summary_status(db, session.id, "ignored")
    assert ignored.summary_status == "ignored"

    with pytest.raises(ValueError, match="bad summary status"):
        store.set_task_session_summary_status(db, session.id, "skip")


def test_command_journal_lists_newest_first_and_prunes(why_home: Path) -> None:
    db = ensure_ready()
    now = datetime.now(UTC)
    old = (now - timedelta(hours=25)).isoformat(timespec="seconds")
    first = (now - timedelta(minutes=2)).isoformat(timespec="seconds")
    second = (now - timedelta(minutes=1)).isoformat(timespec="seconds")

    store.add_command_journal_entry(
        db,
        command="old command",
        cwd="/tmp/demo",
        shell="zsh",
        exit_code=0,
        ran_at=old,
    )
    store.add_command_journal_entry(
        db,
        command="first command",
        cwd="/tmp/demo",
        shell="zsh",
        exit_code=0,
        ran_at=first,
    )
    store.add_command_journal_entry(
        db,
        command="second command",
        cwd="/tmp/demo",
        shell="zsh",
        exit_code=1,
        ran_at=second,
    )

    assert [entry.command for entry in store.list_recent_command_journal(db, limit=3)] == [
        "second command",
        "first command",
        "old command",
    ]

    store.prune_command_journal(db, max_commands=1, max_age_hours=24)

    remaining = store.list_recent_command_journal(db, limit=10)
    assert [entry.command for entry in remaining] == ["second command"]


def test_start_follow_fails_when_session_active(why_home: Path) -> None:
    db = ensure_ready()
    session = start_follow_session(
        db,
        title="Install Postgres",
        project="demo",
        shell="zsh",
        cwd="/tmp/demo",
    )

    with pytest.raises(RuntimeError, match=f"session #{session.id} is already active"):
        start_follow_session(
            db,
            title="Second session",
            project=None,
            shell="zsh",
            cwd="/tmp/demo",
        )


def test_record_command_event_appends_to_journal_and_active_session(why_home: Path) -> None:
    db = ensure_ready()
    session = start_follow_session(
        db,
        title="Install Postgres",
        project="demo",
        shell="zsh",
        cwd="/tmp/demo",
    )

    record_command_event(
        db,
        command="API_TOKEN=secret brew install postgresql@16",
        cwd="/tmp/demo",
        shell="zsh",
        exit_code=0,
    )

    journal = store.list_recent_command_journal(db, limit=1)
    assert len(journal) == 1
    assert "TOKEN=[REDACTED]" in journal[0].command

    commands = store.list_task_session_commands(db, session.id)
    assert len(commands) == 1
    assert commands[0].command == journal[0].command


def test_create_recall_session_copies_last_n_journal_commands(why_home: Path) -> None:
    db = ensure_ready()
    for cmd in ("one", "two", "three"):
        store.add_command_journal_entry(
            db,
            command=cmd,
            cwd="/tmp/demo",
            shell="zsh",
            exit_code=0,
        )

    session = create_recall_session(db, limit=2, title="Recall task")

    assert session.status == "closed"
    assert session.source == "recall"
    commands = store.list_task_session_commands(db, session.id)
    assert [cmd.command for cmd in commands] == ["two", "three"]


def test_parse_selection_accepts_ranges_and_commas() -> None:
    assert parse_selection("1-3,5", max_position=5) == {1, 2, 3, 5}


def test_parse_selection_rejects_out_of_range() -> None:
    with pytest.raises(ValueError, match="out of range"):
        parse_selection("1,6", max_position=5)


def test_concurrent_appends_get_distinct_positions(why_home: Path) -> None:
    """Two terminals recording into one follow session must not collide.

    Regression test: position was computed by a SELECT in autocommit, then used
    by a separate INSERT, so the read-then-write was not atomic. Duplicate
    positions make list_task_session_commands (and therefore the LLM transcript)
    nondeterministically ordered.
    """
    import threading

    db = ensure_ready()
    user = store.get_solo_user(db)
    device = store.get_solo_device(db)
    assert user is not None and device is not None
    session = store.create_task_session(
        db,
        user_id=user.id,
        device_id=device.id,
        source="follow",
        status="active",
        title="race",
        project=None,
        shell="zsh",
        cwd_start="/tmp",
    )

    def append(n: int) -> None:
        for i in range(20):
            store.append_task_session_command(
                db,
                session.id,
                command=f"cmd-{n}-{i}",
                cwd="/tmp",
                exit_code=0,
                started_at="2026-08-08T00:00:00+00:00",
            )

    threads = [threading.Thread(target=append, args=(n,)) for n in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    rows = store.list_task_session_commands(db, session.id)
    positions = [r.position for r in rows]
    assert len(rows) == 120, f"lost writes: {len(rows)}"
    assert len(set(positions)) == 120, (
        f"duplicate positions: {len(positions) - len(set(positions))} collisions"
    )


def _session_with_summary(db):
    user = store.get_solo_user(db)
    device = store.get_solo_device(db)
    assert user is not None and device is not None
    s = store.create_task_session(
        db, user_id=user.id, device_id=device.id, source="follow", status="closed",
        title="t", project=None, shell="zsh", cwd_start="/tmp",
    )
    store.append_task_session_command(
        db, s.id, command="echo hi", cwd="/tmp", exit_code=0,
        started_at="2026-08-08T00:00:00+00:00",
    )
    store.save_task_session_summary(
        db, s.id, provider="p", model="m", endpoint="e", prompt_version=1,
        input_hash="h", summary_markdown="# Recap",
    )
    return s


def test_soft_delete_task_session_hides_it(why_home: Path) -> None:
    db = ensure_ready()
    s = _session_with_summary(db)

    store.soft_delete_task_session(db, s.id)

    assert store.get_task_session(db, s.id) is None
    assert store.list_task_sessions(db) == []


def test_soft_deleted_session_is_not_reported_as_updated(why_home: Path) -> None:
    """Regression (#19): the UPDATE filtered deleted=0 but the SELECT did not, so a
    no-op write returned a stale row and the caller believed it had succeeded.
    """
    db = ensure_ready()
    s = _session_with_summary(db)
    store.soft_delete_task_session(db, s.id)

    for call in (
        lambda: store.close_task_session(db, s.id, cwd_end="/tmp"),
        lambda: store.cancel_task_session(db, s.id),
        lambda: store.set_task_session_summary_status(db, s.id, "ignored"),
    ):
        try:
            call()
        except KeyError:
            continue
        raise AssertionError("a soft-deleted session was reported as updated")


def test_purge_task_session_cascades(why_home: Path) -> None:
    """Hard delete must take its commands and summaries with it."""
    db = ensure_ready()
    s = _session_with_summary(db)
    assert store.list_task_session_commands(db, s.id) != []

    store.purge_task_session(db, s.id)

    assert store.get_task_session(db, s.id) is None
    assert store.list_task_session_commands(db, s.id) == []
    assert store.list_task_session_summaries(db, s.id) == []
