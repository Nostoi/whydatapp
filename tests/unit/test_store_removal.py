"""Tests for store removal functions: mark_removed, create_removal, show_removed filter."""
from __future__ import annotations

from pathlib import Path

import pytest

from why import store
from why.schema import migrate
from why.store import Install, InstallFilters


@pytest.fixture
def db(tmp_path: Path) -> Path:
    p = tmp_path / "data.db"
    migrate(p)
    return p


def _user_device(db: Path) -> tuple[str, str]:
    user = store.get_solo_user(db) or store.create_user(db, display_name="t")
    device = store.get_solo_device(db) or store.create_device(db, hostname="h")
    return user.id, device.id


def _make_install(db: Path, **overrides: object) -> Install:
    uid, did = _user_device(db)
    payload: dict[str, object] = dict(
        command="brew install ripgrep",
        package_name="ripgrep",
        manager="brew",
        install_dir="/tmp",
        resolved_path=None,
        exit_code=0,
        user_id=uid,
        device_id=did,
    )
    payload.update(overrides)
    return store.create_install(db, **payload)


class TestMarkRemoved:
    def test_sets_removed_at(self, db: Path) -> None:
        inst = _make_install(db)
        updated = store.mark_removed(db, inst.id, removed_at="2026-05-01T12:00:00+00:00")
        assert updated.removed_at == "2026-05-01T12:00:00+00:00"

    def test_without_reason_leaves_metadata_incomplete(self, db: Path) -> None:
        inst = _make_install(db)
        updated = store.mark_removed(db, inst.id, removed_at="2026-05-01T12:00:00+00:00")
        assert updated.metadata_complete == 0

    def test_with_reason_sets_why_and_completes_metadata(self, db: Path) -> None:
        inst = _make_install(db)
        updated = store.mark_removed(
            db, inst.id,
            removed_at="2026-05-01T12:00:00+00:00",
            removal_reason="switching to ag",
        )
        assert updated.why == "switching to ag"
        assert updated.metadata_complete == 1

    def test_raises_for_missing_id(self, db: Path) -> None:
        with pytest.raises(KeyError):
            store.mark_removed(db, 99999, removed_at="2026-05-01T12:00:00+00:00")


class TestCreateRemoval:
    def test_creates_row_with_removed_at_and_null_disposition(self, db: Path) -> None:
        uid, did = _user_device(db)
        inst = store.create_removal(
            db,
            command="brew uninstall ripgrep",
            manager="brew",
            package_name="ripgrep",
            install_dir="/tmp",
            removed_at="2026-05-01T12:00:00+00:00",
            user_id=uid,
            device_id=did,
        )
        assert inst.removed_at == "2026-05-01T12:00:00+00:00"
        assert inst.disposition is None
        assert inst.metadata_complete == 0

    def test_with_reason_marks_complete(self, db: Path) -> None:
        uid, did = _user_device(db)
        inst = store.create_removal(
            db,
            command="brew uninstall ripgrep",
            manager="brew",
            package_name="ripgrep",
            install_dir="/tmp",
            removed_at="2026-05-01T12:00:00+00:00",
            removal_reason="no longer needed",
            user_id=uid,
            device_id=did,
        )
        assert inst.why == "no longer needed"
        assert inst.metadata_complete == 1


class TestShowRemovedFilter:
    def test_removed_rows_hidden_by_default(self, db: Path) -> None:
        inst = _make_install(db)
        store.mark_removed(db, inst.id, removed_at="2026-05-01T12:00:00+00:00")
        rows = store.list_installs(db, InstallFilters())
        assert all(r.id != inst.id for r in rows)

    def test_show_removed_includes_removed_rows(self, db: Path) -> None:
        inst = _make_install(db)
        store.mark_removed(db, inst.id, removed_at="2026-05-01T12:00:00+00:00")
        rows = store.list_installs(db, InstallFilters(show_removed=True))
        assert any(r.id == inst.id for r in rows)

    def test_non_removed_rows_visible_by_default(self, db: Path) -> None:
        inst = _make_install(db)
        rows = store.list_installs(db, InstallFilters())
        assert any(r.id == inst.id for r in rows)
