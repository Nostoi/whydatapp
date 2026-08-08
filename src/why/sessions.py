from __future__ import annotations

import os
from pathlib import Path

from why import store
from why.config import load_config
from why.redact import redact


def start_follow_session(
    db: Path,
    *,
    title: str | None,
    project: str | None,
    shell: str | None,
    cwd: str | None = None,
) -> store.TaskSession:
    user = store.get_solo_user(db)
    device = store.get_solo_device(db)
    if user is None or device is None:
        raise RuntimeError("why database is not initialized")
    active = store.get_active_task_session(db)
    if active is not None:
        raise RuntimeError(f"session #{active.id} is already active")
    return store.create_task_session(
        db,
        user_id=user.id,
        device_id=device.id,
        source="follow",
        status="active",
        title=title,
        project=project,
        shell=shell,
        cwd_start=cwd or os.getcwd(),
    )


def stop_follow_session(db: Path, *, cwd: str | None = None) -> store.TaskSession:
    active = store.get_active_task_session(db)
    if active is None:
        raise RuntimeError("no active follow session")
    return store.close_task_session(db, active.id, cwd_end=cwd or os.getcwd())


def cancel_follow_session(db: Path) -> store.TaskSession:
    active = store.get_active_task_session(db)
    if active is None:
        raise RuntimeError("no active follow session")
    return store.cancel_task_session(db, active.id)


def record_command_event(
    db: Path,
    *,
    command: str,
    cwd: str,
    shell: str | None,
    exit_code: int | None,
) -> None:
    cfg = load_config()
    redacted = redact(command)
    entry = store.add_command_journal_entry(
        db,
        command=redacted,
        cwd=cwd,
        shell=shell,
        exit_code=exit_code,
    )
    store.prune_command_journal(
        db,
        max_commands=int(cfg["journal"]["max_commands"]),
        max_age_hours=int(cfg["journal"]["max_age_hours"]),
    )
    active = store.get_active_task_session(db)
    if active is not None:
        store.append_task_session_command(
            db,
            active.id,
            command=redacted,
            cwd=cwd,
            exit_code=exit_code,
            started_at=entry.ran_at,
        )


def create_recall_session(
    db: Path,
    *,
    limit: int,
    title: str | None = None,
    selected_positions: set[int] | None = None,
) -> store.TaskSession:
    user = store.get_solo_user(db)
    device = store.get_solo_device(db)
    if user is None or device is None:
        raise RuntimeError("why database is not initialized")
    entries = list(reversed(store.list_recent_command_journal(db, limit=limit)))
    if selected_positions is not None:
        entries = [entry for index, entry in enumerate(entries, 1) if index in selected_positions]
    if not entries:
        # Never create a zero-command session: it would be advertised via
        # `why sessions show/summarize` as though it held a transcript.
        raise ValueError("No recent commands to recall.")
    session = store.create_task_session(
        db,
        user_id=user.id,
        device_id=device.id,
        source="recall",
        status="active",
        title=title,
        project=None,
        shell=entries[-1].shell if entries else None,
        cwd_start=entries[0].cwd if entries else os.getcwd(),
    )
    for entry in entries:
        store.append_task_session_command(
            db,
            session.id,
            command=entry.command,
            cwd=entry.cwd,
            exit_code=entry.exit_code,
            started_at=entry.ran_at,
        )
    cwd_end = entries[-1].cwd if entries else os.getcwd()
    return store.close_task_session(db, session.id, cwd_end=cwd_end)


def parse_selection(selection: str, *, max_position: int) -> set[int]:
    selected: set[int] = set()
    for raw_part in selection.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start = int(start_s)
            end = int(end_s)
            if start > end:
                raise ValueError("range start must be before range end")
            selected.update(range(start, end + 1))
        else:
            selected.add(int(part))
    if not selected:
        raise ValueError("no commands selected")
    if min(selected) < 1 or max(selected) > max_position:
        raise ValueError("selection out of range")
    return selected
