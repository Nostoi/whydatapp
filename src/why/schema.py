from __future__ import annotations

import shutil
import sqlite3
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def current_version(db_path: Path) -> int:
    if not db_path.exists() or db_path.stat().st_size == 0:
        return 0
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()
        if not row:
            return 0
        v = conn.execute("SELECT version FROM schema_version").fetchone()
        return int(v[0]) if v else 0


def _backup(db_path: Path, backups_dir: Path) -> None:
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    shutil.copy2(db_path, backups_dir / f"data.{stamp}.db")


_MIGRATION_FILES = {
    1: "001_init.sql",
    2: "002_reinstall_columns.sql",
    3: "003_purposes.sql",
    4: "004_command_history.sql",
}


def _read_migration(n: int) -> str:
    filename = _MIGRATION_FILES[n]
    return resources.files("why.migrations").joinpath(filename).read_text()


MIGRATIONS = {
    1: lambda: _read_migration(1),
    2: lambda: _read_migration(2),
    3: lambda: _read_migration(3),
    4: lambda: _read_migration(4),
}


def migrate(db_path: Path, backups_dir: Path | None = None) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    cur = current_version(db_path)
    target = max(MIGRATIONS)
    if cur == target:
        return
    if cur > 0 and backups_dir is not None:
        _backup(db_path, backups_dir)
    with _connect(db_path) as conn:
        for v in range(cur + 1, target + 1):
            conn.executescript(MIGRATIONS[v]())
            conn.execute("UPDATE schema_version SET version = ?", (v,))
        conn.commit()
