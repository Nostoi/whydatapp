from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id() -> str:
    return str(uuid.uuid4())


@contextmanager
def _conn(db_path: Path) -> Iterator[sqlite3.Connection]:
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    # Declared explicitly rather than relying on sqlite3.connect()'s default
    # timeout=5.0, which silently disappears if this connect call is ever changed.
    c.execute("PRAGMA busy_timeout=5000")
    try:
        yield c
        c.commit()
    finally:
        c.close()


@dataclass(frozen=True)
class User:
    id: str
    email: str | None
    display_name: str | None
    created_at: str


@dataclass(frozen=True)
class Device:
    id: str
    hostname: str
    label: str | None
    created_at: str
    last_seen_at: str


def create_user(db: Path, *, display_name: str | None = None, email: str | None = None) -> User:
    uid = _new_id()
    now = _now()
    with _conn(db) as c:
        c.execute(
            "INSERT INTO users(id,email,display_name,created_at) VALUES (?,?,?,?)",
            (uid, email, display_name, now),
        )
    return User(uid, email, display_name, now)


def get_user(db: Path, uid: str) -> User | None:
    with _conn(db) as c:
        r = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return User(**dict(r)) if r else None


def get_solo_user(db: Path) -> User | None:
    """Return the single user row in MVP single-user mode, or None."""
    with _conn(db) as c:
        r = c.execute("SELECT * FROM users LIMIT 1").fetchone()
    return User(**dict(r)) if r else None


def create_device(db: Path, *, hostname: str, label: str | None = None) -> Device:
    did = _new_id()
    now = _now()
    with _conn(db) as c:
        c.execute(
            "INSERT INTO devices(id,hostname,label,created_at,last_seen_at) VALUES (?,?,?,?,?)",
            (did, hostname, label, now, now),
        )
    return Device(did, hostname, label, now, now)


def get_device(db: Path, did: str) -> Device | None:
    with _conn(db) as c:
        r = c.execute("SELECT * FROM devices WHERE id=?", (did,)).fetchone()
    return Device(**dict(r)) if r else None


def get_solo_device(db: Path) -> Device | None:
    with _conn(db) as c:
        r = c.execute("SELECT * FROM devices LIMIT 1").fetchone()
    return Device(**dict(r)) if r else None


def touch_device(db: Path, did: str) -> None:
    with _conn(db) as c:
        c.execute("UPDATE devices SET last_seen_at=? WHERE id=?", (_now(), did))


def upsert_project(db: Path, name: str) -> None:
    with _conn(db) as c:
        c.execute(
            "INSERT OR IGNORE INTO projects(name, created_at) VALUES (?, ?)",
            (name, _now()),
        )


def list_projects(db: Path) -> list[str]:
    with _conn(db) as c:
        rows = c.execute("SELECT name FROM projects ORDER BY name").fetchall()
    return [r["name"] for r in rows]


@dataclass(frozen=True)
class Install:
    id: int
    sync_id: str
    user_id: str
    device_id: str
    command: str
    package_name: str | None
    manager: str
    install_dir: str
    resolved_path: str | None
    installed_at: str
    exit_code: int
    display_name: str | None
    what_it_does: str | None
    project: str | None
    why: str | None
    disposition: str | None
    notes: str | None
    source_url: str | None
    metadata_complete: int
    reviewed_at: str | None
    removed_at: str | None
    updated_at: str
    deleted: int
    reinstall_count: int
    last_installed_at: str | None


@dataclass(frozen=True)
class TaskSession:
    id: int
    sync_id: str
    user_id: str
    device_id: str
    title: str | None
    project: str | None
    source: str
    status: str
    shell: str | None
    started_at: str
    ended_at: str | None
    cwd_start: str | None
    cwd_end: str | None
    summary_status: str
    created_at: str
    updated_at: str
    deleted: int


@dataclass(frozen=True)
class TaskSessionCommand:
    id: int
    session_id: int
    position: int
    command: str
    cwd: str
    exit_code: int | None
    started_at: str
    ended_at: str | None
    matched_install_id: int | None
    redaction_version: int


@dataclass(frozen=True)
class TaskSessionSummary:
    id: int
    session_id: int
    provider: str
    model: str
    endpoint: str | None
    prompt_version: int
    input_hash: str
    summary_markdown: str
    created_at: str


@dataclass(frozen=True)
class CommandJournalEntry:
    id: int
    command: str
    cwd: str
    shell: str | None
    exit_code: int | None
    ran_at: str


@dataclass(frozen=True)
class InstallFilters:
    disposition: str | None = None
    project: str | None = None
    manager: str | None = None
    device_id: str | None = None
    incomplete_only: bool = False
    complete_only: bool = False  # when True, only rows with metadata_complete=1
    include_deleted: bool = False
    show_removed: bool = False  # when True, include rows with removed_at set
    limit: int = 1000
    offset: int = 0
    order_by: str = "installed_at"
    order_dir: str = "desc"


_ALLOWED_ORDER = {"installed_at", "manager", "project", "disposition", "display_name", "id"}


def _row_to_install(r: sqlite3.Row) -> Install:
    return Install(**dict(r))


def create_install(
    db: Path,
    *,
    user_id: str,
    device_id: str,
    command: str,
    package_name: str | None,
    manager: str,
    install_dir: str,
    resolved_path: str | None,
    exit_code: int,
    installed_at: str | None = None,
) -> Install:
    sid = _new_id()
    now = _now()
    inst_at = installed_at or now
    with _conn(db) as c:
        cur = c.execute(
            """INSERT INTO installs(
                sync_id,user_id,device_id,command,package_name,manager,install_dir,
                resolved_path,installed_at,exit_code,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (sid, user_id, device_id, command, package_name, manager, install_dir,
             resolved_path, inst_at, exit_code, now),
        )
        new_id = cur.lastrowid
        r = c.execute("SELECT * FROM installs WHERE id=?", (new_id,)).fetchone()
    return _row_to_install(r)


_UPDATABLE = {
    "display_name", "what_it_does", "project", "why", "disposition", "notes",
    "source_url", "metadata_complete", "reviewed_at", "removed_at",
    "package_name", "resolved_path", "reinstall_count", "last_installed_at",
}


def update_install(db: Path, install_id: int, **fields: object) -> Install:
    bad = set(fields) - _UPDATABLE
    if bad:
        raise ValueError(f"unknown fields: {bad}")
    if not fields:
        raise ValueError("no fields to update")
    fields["updated_at"] = _now()
    sets = ",".join(f"{k}=?" for k in fields)
    params = list(fields.values()) + [install_id]
    with _conn(db) as c:
        c.execute(f"UPDATE installs SET {sets} WHERE id=?", params)
        r = c.execute("SELECT * FROM installs WHERE id=?", (install_id,)).fetchone()
    if not r:
        raise KeyError(install_id)
    return _row_to_install(r)


def get_install(db: Path, install_id: int) -> Install | None:
    with _conn(db) as c:
        r = c.execute("SELECT * FROM installs WHERE id=?", (install_id,)).fetchone()
    return _row_to_install(r) if r else None


def list_installs(db: Path, f: InstallFilters) -> list[Install]:
    if f.order_by not in _ALLOWED_ORDER:
        raise ValueError(f"bad order_by: {f.order_by}")
    direction = "DESC" if f.order_dir.lower() == "desc" else "ASC"
    where = []
    params: list[object] = []
    if not f.include_deleted:
        where.append("deleted=0")
    if not f.show_removed:
        where.append("removed_at IS NULL")
    if f.disposition:
        where.append("disposition=?")
        params.append(f.disposition)
    if f.project:
        where.append("project=?")
        params.append(f.project)
    if f.manager:
        where.append("manager=?")
        params.append(f.manager)
    if f.device_id:
        where.append("device_id=?")
        params.append(f.device_id)
    if f.incomplete_only:
        where.append("metadata_complete=0")
    elif f.complete_only:
        where.append("metadata_complete=1")
    sql = "SELECT * FROM installs"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {f.order_by} {direction} LIMIT ? OFFSET ?"
    params += [f.limit, f.offset]
    with _conn(db) as c:
        rows = c.execute(sql, params).fetchall()
    return [_row_to_install(r) for r in rows]


def search_installs(db: Path, query: str, limit: int = 100) -> list[Install]:
    with _conn(db) as c:
        rows = c.execute(
            """SELECT installs.* FROM installs
               JOIN installs_fts ON installs_fts.rowid=installs.id
               WHERE installs_fts MATCH ? AND installs.deleted=0
               ORDER BY rank LIMIT ?""",
            (query, limit),
        ).fetchall()
    return [_row_to_install(r) for r in rows]


def soft_delete_install(db: Path, install_id: int) -> None:
    with _conn(db) as c:
        c.execute(
            "UPDATE installs SET deleted=1, updated_at=? WHERE id=?",
            (_now(), install_id),
        )


def recent_duplicate_exists(
    db: Path, *, command: str, install_dir: str, within_seconds: int
) -> bool:
    with _conn(db) as c:
        r = c.execute(
            """SELECT 1 FROM installs
               WHERE command=? AND install_dir=?
                 AND deleted=0
                 AND installed_at >= datetime('now', ?)
               LIMIT 1""",
            (command, install_dir, f"-{within_seconds} seconds"),
        ).fetchone()
    return r is not None


def stats_by_disposition(db: Path, *, include_removed: bool = False) -> dict[str, int]:
    """Count of installs grouped by disposition.

    By default excludes uninstalled rows (``removed_at IS NOT NULL``) so the
    counts match what the default web/CLI views actually render. Pass
    ``include_removed=True`` to include them (e.g. for an All-time stat).
    """
    where = "deleted=0"
    if not include_removed:
        where += " AND removed_at IS NULL"
    with _conn(db) as c:
        rows = c.execute(
            f"""SELECT COALESCE(disposition,'(unset)') AS d, COUNT(*) AS n
                FROM installs WHERE {where} GROUP BY d"""
        ).fetchall()
    return {r["d"]: r["n"] for r in rows}


def count_removed(db: Path) -> int:
    with _conn(db) as c:
        r = c.execute(
            "SELECT COUNT(*) AS n FROM installs WHERE deleted=0 AND removed_at IS NOT NULL"
        ).fetchone()
    return int(r["n"]) if r else 0


def stats_by_manager(db: Path) -> dict[str, int]:
    with _conn(db) as c:
        rows = c.execute(
            "SELECT manager, COUNT(*) AS n FROM installs WHERE deleted=0 GROUP BY manager"
        ).fetchall()
    return {r["manager"]: r["n"] for r in rows}


def stats_by_project(db: Path, limit: int = 10) -> list[tuple[str, int]]:
    with _conn(db) as c:
        rows = c.execute(
            """SELECT COALESCE(project,'(unset)') AS p, COUNT(*) AS n
               FROM installs WHERE deleted=0 GROUP BY p ORDER BY n DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [(r["p"], r["n"]) for r in rows]


def installs_per_month(db: Path, months: int = 12) -> list[tuple[str, int]]:
    with _conn(db) as c:
        rows = c.execute(
            """SELECT substr(installed_at,1,7) AS m, COUNT(*) AS n
               FROM installs WHERE deleted=0
               GROUP BY m ORDER BY m DESC LIMIT ?""",
            (months,),
        ).fetchall()
    return [(r["m"], r["n"]) for r in rows]


def stale_review_queue(db: Path) -> list[Install]:
    """Skipped/incomplete + stale experimental + stale remove."""
    with _conn(db) as c:
        rows = c.execute(
            """SELECT * FROM installs WHERE deleted=0 AND (
                 metadata_complete=0
                 OR (disposition='experimental' AND installed_at < datetime('now','-30 days'))
                 OR (disposition='remove' AND removed_at IS NULL
                     AND installed_at < datetime('now','-14 days'))
               ) ORDER BY installed_at ASC"""
        ).fetchall()
    return [_row_to_install(r) for r in rows]


def list_skipped(db: Path) -> list[Install]:
    with _conn(db) as c:
        rows = c.execute(
            "SELECT * FROM installs"
            " WHERE deleted=0 AND metadata_complete=0"
            " ORDER BY installed_at ASC"
        ).fetchall()
    return [_row_to_install(r) for r in rows]


def find_existing_install(
    db: Path, *, manager: str, package_name: str
) -> Install | None:
    """Return the most recent non-deleted install for (manager, package_name), or None."""
    with _conn(db) as c:
        r = c.execute(
            """SELECT * FROM installs
               WHERE manager=? AND package_name=? AND deleted=0
               ORDER BY installed_at DESC
               LIMIT 1""",
            (manager, package_name),
        ).fetchone()
    return _row_to_install(r) if r else None


def record_reinstall(db: Path, install_id: int) -> Install:
    """Bump reinstall_count, set last_installed_at and updated_at. Returns updated row."""
    now = _now()
    with _conn(db) as c:
        c.execute(
            """UPDATE installs
               SET reinstall_count = reinstall_count + 1,
                   last_installed_at = ?,
                   updated_at = ?
               WHERE id = ?""",
            (now, now, install_id),
        )
        r = c.execute("SELECT * FROM installs WHERE id=?", (install_id,)).fetchone()
    if not r:
        raise KeyError(install_id)
    return _row_to_install(r)


# ---------------------------------------------------------------------------
# Purposes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Purpose:
    key: str
    label: str
    color: str
    sort_order: int
    built_in: bool


def _row_to_purpose(r: sqlite3.Row) -> Purpose:
    return Purpose(
        key=r["key"],
        label=r["label"],
        color=r["color"],
        sort_order=r["sort_order"],
        built_in=bool(r["built_in"]),
    )


def list_purposes(db: Path) -> list[Purpose]:
    """Return all purposes ordered by sort_order."""
    with _conn(db) as c:
        rows = c.execute(
            "SELECT * FROM purposes ORDER BY sort_order, key"
        ).fetchall()
    return [_row_to_purpose(r) for r in rows]


def get_purpose(db: Path, key: str) -> Purpose | None:
    with _conn(db) as c:
        r = c.execute("SELECT * FROM purposes WHERE key=?", (key,)).fetchone()
    return _row_to_purpose(r) if r else None


def create_purpose(
    db: Path, *, key: str, label: str, color: str = "#6b7280", sort_order: int = 99
) -> Purpose:
    with _conn(db) as c:
        c.execute(
            "INSERT INTO purposes(key, label, color, sort_order, built_in) VALUES (?,?,?,?,0)",
            (key, label, color, sort_order),
        )
    return Purpose(key=key, label=label, color=color, sort_order=sort_order, built_in=False)


def update_purpose(
    db: Path,
    key: str,
    *,
    label: str | None = None,
    color: str | None = None,
    sort_order: int | None = None,
) -> Purpose:
    fields: dict[str, object] = {}
    if label is not None:
        fields["label"] = label
    if color is not None:
        fields["color"] = color
    if sort_order is not None:
        fields["sort_order"] = sort_order
    if not fields:
        raise ValueError("no fields to update")
    sets = ", ".join(f"{k}=?" for k in fields)
    params = list(fields.values()) + [key]
    with _conn(db) as c:
        c.execute(f"UPDATE purposes SET {sets} WHERE key=?", params)
        r = c.execute("SELECT * FROM purposes WHERE key=?", (key,)).fetchone()
    if not r:
        raise KeyError(key)
    return _row_to_purpose(r)


def delete_purpose(db: Path, key: str) -> None:
    """Delete a purpose. Raises ValueError if it is built-in."""
    with _conn(db) as c:
        r = c.execute("SELECT built_in FROM purposes WHERE key=?", (key,)).fetchone()
        if r is None:
            raise KeyError(key)
        if r["built_in"]:
            raise ValueError(f"cannot delete built-in purpose '{key}'")
        c.execute("DELETE FROM purposes WHERE key=?", (key,))


# ---------------------------------------------------------------------------
# Command history
# ---------------------------------------------------------------------------

_HISTORY_LIMIT = 10  # max commands stored per install


def save_command_history(db: Path, install_id: int, commands: list[str]) -> None:
    """Store the ring-buffer commands that preceded *install_id*.

    *commands* is oldest-first; at most _HISTORY_LIMIT entries are kept.
    Silently no-ops when *commands* is empty.
    """
    if not commands:
        return
    trimmed = commands[-_HISTORY_LIMIT:]
    with _conn(db) as c:
        c.executemany(
            "INSERT INTO command_history (install_id, position, command) VALUES (?,?,?)",
            [(install_id, i, cmd) for i, cmd in enumerate(trimmed)],
        )


def get_command_history(db: Path, install_id: int) -> list[str]:
    """Return commands for *install_id*, oldest-first. Empty list if none."""
    with _conn(db) as c:
        rows = c.execute(
            "SELECT command FROM command_history WHERE install_id=? ORDER BY position",
            (install_id,),
        ).fetchall()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Task sessions and command journal
# ---------------------------------------------------------------------------

_SUMMARY_STATUSES = {"none", "ignored", "pending", "complete", "failed"}


def _row_to_task_session(r: sqlite3.Row) -> TaskSession:
    return TaskSession(**dict(r))


def _row_to_task_session_command(r: sqlite3.Row) -> TaskSessionCommand:
    return TaskSessionCommand(**dict(r))


def _row_to_task_session_summary(r: sqlite3.Row) -> TaskSessionSummary:
    return TaskSessionSummary(**dict(r))


def _row_to_command_journal_entry(r: sqlite3.Row) -> CommandJournalEntry:
    return CommandJournalEntry(**dict(r))


def create_task_session(
    db: Path,
    *,
    user_id: str,
    device_id: str,
    source: str,
    status: str,
    title: str | None,
    project: str | None,
    shell: str | None,
    cwd_start: str | None,
) -> TaskSession:
    sid = _new_id()
    now = _now()
    with _conn(db) as c:
        cur = c.execute(
            """INSERT INTO task_sessions(
                sync_id,user_id,device_id,title,project,source,status,shell,
                started_at,cwd_start,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                sid,
                user_id,
                device_id,
                title,
                project,
                source,
                status,
                shell,
                now,
                cwd_start,
                now,
                now,
            ),
        )
        new_id = cur.lastrowid
        r = c.execute("SELECT * FROM task_sessions WHERE id=?", (new_id,)).fetchone()
    return _row_to_task_session(r)


def close_task_session(db: Path, session_id: int, *, cwd_end: str | None) -> TaskSession:
    now = _now()
    with _conn(db) as c:
        c.execute(
            """UPDATE task_sessions
               SET status='closed', ended_at=?, cwd_end=?, updated_at=?
               WHERE id=? AND deleted=0""",
            (now, cwd_end, now, session_id),
        )
        r = c.execute(
            "SELECT * FROM task_sessions WHERE id=? AND deleted=0", (session_id,)
        ).fetchone()
    if not r:
        raise KeyError(session_id)
    return _row_to_task_session(r)


def cancel_task_session(db: Path, session_id: int) -> TaskSession:
    now = _now()
    with _conn(db) as c:
        c.execute(
            """UPDATE task_sessions
               SET status='cancelled', ended_at=?, updated_at=?
               WHERE id=? AND deleted=0""",
            (now, now, session_id),
        )
        r = c.execute(
            "SELECT * FROM task_sessions WHERE id=? AND deleted=0", (session_id,)
        ).fetchone()
    if not r:
        raise KeyError(session_id)
    return _row_to_task_session(r)


def soft_delete_task_session(db: Path, session_id: int) -> None:
    """Hide a session, keeping the row as a sync tombstone (mirrors installs)."""
    with _conn(db) as c:
        c.execute(
            "UPDATE task_sessions SET deleted=1, updated_at=? WHERE id=?",
            (_now(), session_id),
        )


def purge_task_session(db: Path, session_id: int) -> None:
    """Irreversibly remove a session and, via ON DELETE CASCADE, its commands and
    summaries. For transcripts the user wants genuinely off the machine, where a
    soft-deleted row on disk would not be an honest answer.
    """
    with _conn(db) as c:
        c.execute("DELETE FROM task_sessions WHERE id=?", (session_id,))


def get_active_task_session(db: Path) -> TaskSession | None:
    with _conn(db) as c:
        r = c.execute(
            """SELECT * FROM task_sessions
               WHERE status='active' AND deleted=0
               ORDER BY started_at DESC, id DESC LIMIT 1"""
        ).fetchone()
    return _row_to_task_session(r) if r else None


def get_task_session(db: Path, session_id: int) -> TaskSession | None:
    with _conn(db) as c:
        r = c.execute(
            "SELECT * FROM task_sessions WHERE id=? AND deleted=0",
            (session_id,),
        ).fetchone()
    return _row_to_task_session(r) if r else None


def list_task_sessions(
    db: Path, *, summary_status: str | None = None, limit: int = 100
) -> list[TaskSession]:
    where = ["deleted=0"]
    params: list[object] = []
    if summary_status is not None:
        where.append("summary_status=?")
        params.append(summary_status)
    sql = "SELECT * FROM task_sessions WHERE " + " AND ".join(where)
    sql += " ORDER BY started_at DESC, id DESC LIMIT ?"
    params.append(limit)
    with _conn(db) as c:
        rows = c.execute(sql, params).fetchall()
    return [_row_to_task_session(r) for r in rows]


def append_task_session_command(
    db: Path,
    session_id: int,
    *,
    command: str,
    cwd: str,
    exit_code: int | None,
    started_at: str,
    ended_at: str | None = None,
    matched_install_id: int | None = None,
) -> TaskSessionCommand:
    with _conn(db) as c:
        # The position is computed inside the INSERT so the read and the write happen
        # as one statement under SQLite's write lock. A separate SELECT then INSERT
        # races when two terminals record into the same follow session, producing
        # duplicate positions and a nondeterministically ordered transcript.
        cur = c.execute(
            """INSERT INTO task_session_commands(
                session_id,position,command,cwd,exit_code,started_at,ended_at,
                matched_install_id)
               VALUES (
                 ?,
                 (SELECT COALESCE(MAX(position), -1) + 1
                    FROM task_session_commands WHERE session_id=?),
                 ?,?,?,?,?,?)""",
            (
                session_id,
                session_id,
                command,
                cwd,
                exit_code,
                started_at,
                ended_at,
                matched_install_id,
            ),
        )
        new_id = cur.lastrowid
        r = c.execute(
            "SELECT * FROM task_session_commands WHERE id=?",
            (new_id,),
        ).fetchone()
    return _row_to_task_session_command(r)


def list_task_session_commands(db: Path, session_id: int) -> list[TaskSessionCommand]:
    with _conn(db) as c:
        rows = c.execute(
            """SELECT * FROM task_session_commands
               WHERE session_id=? ORDER BY position""",
            (session_id,),
        ).fetchall()
    return [_row_to_task_session_command(r) for r in rows]


def save_task_session_summary(
    db: Path,
    session_id: int,
    *,
    provider: str,
    model: str,
    endpoint: str | None,
    prompt_version: int,
    input_hash: str,
    summary_markdown: str,
) -> TaskSessionSummary:
    now = _now()
    with _conn(db) as c:
        cur = c.execute(
            """INSERT INTO task_session_summaries(
                session_id,provider,model,endpoint,prompt_version,input_hash,
                summary_markdown,created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                session_id,
                provider,
                model,
                endpoint,
                prompt_version,
                input_hash,
                summary_markdown,
                now,
            ),
        )
        c.execute(
            """UPDATE task_sessions
               SET summary_status='complete', updated_at=?
               WHERE id=? AND deleted=0""",
            (now, session_id),
        )
        new_id = cur.lastrowid
        r = c.execute(
            "SELECT * FROM task_session_summaries WHERE id=?",
            (new_id,),
        ).fetchone()
    return _row_to_task_session_summary(r)


def list_task_session_summaries(db: Path, session_id: int) -> list[TaskSessionSummary]:
    with _conn(db) as c:
        rows = c.execute(
            """SELECT * FROM task_session_summaries
               WHERE session_id=? ORDER BY created_at DESC, id DESC""",
            (session_id,),
        ).fetchall()
    return [_row_to_task_session_summary(r) for r in rows]


def set_task_session_summary_status(
    db: Path, session_id: int, status: str
) -> TaskSession:
    if status not in _SUMMARY_STATUSES:
        raise ValueError(f"bad summary status: {status}")
    now = _now()
    with _conn(db) as c:
        c.execute(
            """UPDATE task_sessions
               SET summary_status=?, updated_at=?
               WHERE id=? AND deleted=0""",
            (status, now, session_id),
        )
        r = c.execute(
            "SELECT * FROM task_sessions WHERE id=? AND deleted=0", (session_id,)
        ).fetchone()
    if not r:
        raise KeyError(session_id)
    return _row_to_task_session(r)


def add_command_journal_entry(
    db: Path,
    *,
    command: str,
    cwd: str,
    shell: str | None,
    exit_code: int | None,
    ran_at: str | None = None,
) -> CommandJournalEntry:
    timestamp = ran_at or _now()
    with _conn(db) as c:
        cur = c.execute(
            """INSERT INTO command_journal(command,cwd,shell,exit_code,ran_at)
               VALUES (?,?,?,?,?)""",
            (command, cwd, shell, exit_code, timestamp),
        )
        new_id = cur.lastrowid
        r = c.execute("SELECT * FROM command_journal WHERE id=?", (new_id,)).fetchone()
    return _row_to_command_journal_entry(r)


def list_recent_command_journal(db: Path, *, limit: int) -> list[CommandJournalEntry]:
    with _conn(db) as c:
        rows = c.execute(
            """SELECT * FROM command_journal
               ORDER BY ran_at DESC, id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [_row_to_command_journal_entry(r) for r in rows]


def prune_command_journal(db: Path, *, max_commands: int, max_age_hours: int) -> None:
    cutoff = (datetime.now(UTC) - timedelta(hours=max_age_hours)).isoformat(timespec="seconds")
    with _conn(db) as c:
        c.execute("DELETE FROM command_journal WHERE ran_at < ?", (cutoff,))
        if max_commands <= 0:
            c.execute("DELETE FROM command_journal")
            return
        c.execute(
            """DELETE FROM command_journal
               WHERE id NOT IN (
                 SELECT id FROM command_journal
                 ORDER BY ran_at DESC, id DESC LIMIT ?
               )""",
            (max_commands,),
        )


# ---------------------------------------------------------------------------
# Removal tracking
# ---------------------------------------------------------------------------

def mark_removed(
    db: Path,
    install_id: int,
    *,
    removed_at: str,
    removal_reason: str | None = None,
) -> Install:
    """Set removed_at on an install row.

    Optionally records *removal_reason* into the ``why`` field.
    Sets ``metadata_complete=1`` when a reason is provided, leaves it
    untouched (0) otherwise so the entry surfaces in the review queue.
    Returns the updated Install.
    """
    now = _now()
    with _conn(db) as c:
        if removal_reason is not None:
            c.execute(
                """UPDATE installs
                   SET removed_at=?, why=?, metadata_complete=1, updated_at=?
                   WHERE id=?""",
                (removed_at, removal_reason, now, install_id),
            )
        else:
            c.execute(
                """UPDATE installs
                   SET removed_at=?, updated_at=?
                   WHERE id=?""",
                (removed_at, now, install_id),
            )
        r = c.execute("SELECT * FROM installs WHERE id=?", (install_id,)).fetchone()
    if not r:
        raise KeyError(install_id)
    return _row_to_install(r)


def create_removal(
    db: Path,
    *,
    command: str,
    manager: str,
    package_name: str,
    install_dir: str,
    removed_at: str,
    removal_reason: str | None = None,
    user_id: str,
    device_id: str,
) -> Install:
    """Create a new install row representing a removal with no prior install record.

    ``disposition`` (purpose) is left NULL — we don't know why it was installed.
    ``metadata_complete`` is 0 so it surfaces in the review queue.
    ``removed_at`` is set immediately.
    """
    import uuid as _uuid

    now = _now()
    sync_id = str(_uuid.uuid4())
    metadata_complete = 1 if removal_reason is not None else 0
    with _conn(db) as c:
        cur = c.execute(
            """INSERT INTO installs (
                sync_id, user_id, device_id,
                command, package_name, manager, install_dir,
                installed_at, exit_code,
                removed_at, why,
                metadata_complete, updated_at, deleted
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
            (
                sync_id, user_id, device_id,
                command, package_name, manager, install_dir,
                removed_at,   # installed_at approximated to removal time
                0,            # exit_code unknown
                removed_at,
                removal_reason,
                metadata_complete,
                now,
            ),
        )
        row_id = cur.lastrowid
        r = c.execute("SELECT * FROM installs WHERE id=?", (row_id,)).fetchone()
    if not r:
        raise RuntimeError("failed to create removal record")
    return _row_to_install(r)
