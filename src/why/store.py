from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
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
class InstallFilters:
    disposition: str | None = None
    project: str | None = None
    manager: str | None = None
    device_id: str | None = None
    incomplete_only: bool = False
    include_deleted: bool = False
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


def stats_by_disposition(db: Path) -> dict[str, int]:
    with _conn(db) as c:
        rows = c.execute(
            """SELECT COALESCE(disposition,'(unset)') AS d, COUNT(*) AS n
               FROM installs WHERE deleted=0 GROUP BY d"""
        ).fetchall()
    return {r["d"]: r["n"] for r in rows}


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
