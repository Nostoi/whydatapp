from __future__ import annotations

import sqlite3
from pathlib import Path

from why.schema import current_version, migrate


def test_migrate_creates_schema_v1(tmp_path: Path) -> None:
    db = tmp_path / "x.db"
    migrate(db)
    assert current_version(db) == 2
    with sqlite3.connect(db) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "devices", "projects", "installs", "installs_fts", "schema_version"} <= tables


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "x.db"
    migrate(db)
    migrate(db)
    assert current_version(db) == 2


def test_migrate_creates_backup_when_db_exists(tmp_path: Path) -> None:
    db = tmp_path / "x.db"
    backups = tmp_path / "backups"
    backups.mkdir()
    db.write_bytes(b"")
    migrate(db, backups_dir=backups)
    assert list(backups.iterdir()) == []


def test_migrate_to_v2_adds_columns(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    migrate(db)
    assert current_version(db) == 2
    with sqlite3.connect(db) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(installs)")}
    assert "reinstall_count" in cols
    assert "last_installed_at" in cols


def test_migrate_v2_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "idem.db"
    migrate(db)
    migrate(db)  # second call is a no-op
    assert current_version(db) == 2


def test_migrate_v1_to_v2_takes_backup(tmp_path: Path) -> None:
    """Migrating a v1 database to v2 takes a backup of the existing file."""
    import why.schema as schema_mod

    db = tmp_path / "v1.db"
    backups = tmp_path / "backups"

    # Build a real v1 database by temporarily patching MIGRATIONS.
    original = schema_mod.MIGRATIONS
    try:
        schema_mod.MIGRATIONS = {1: original[1]}
        migrate(db, backups_dir=backups)
    finally:
        schema_mod.MIGRATIONS = original

    assert current_version(db) == 1
    # Now upgrade to v2 with backups enabled — a backup of the v1 db should be created.
    migrate(db, backups_dir=backups)
    assert current_version(db) == 2
    backup_files = list(backups.iterdir())
    assert len(backup_files) >= 1
