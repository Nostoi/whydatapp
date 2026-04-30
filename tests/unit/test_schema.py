from __future__ import annotations

import sqlite3
from pathlib import Path

from why.schema import current_version, migrate


def test_migrate_creates_schema_v1(tmp_path: Path) -> None:
    db = tmp_path / "x.db"
    migrate(db)
    assert current_version(db) == 1
    with sqlite3.connect(db) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "devices", "projects", "installs", "installs_fts", "schema_version"} <= tables


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "x.db"
    migrate(db)
    migrate(db)
    assert current_version(db) == 1


def test_migrate_creates_backup_when_db_exists(tmp_path: Path) -> None:
    db = tmp_path / "x.db"
    backups = tmp_path / "backups"
    backups.mkdir()
    db.write_bytes(b"")
    migrate(db, backups_dir=backups)
    assert list(backups.iterdir()) == []
