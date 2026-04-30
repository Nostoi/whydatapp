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


def test_create_and_get_user(db: Path) -> None:
    user = store.create_user(db, display_name="mark")
    assert user.id
    assert user.display_name == "mark"
    fetched = store.get_user(db, user.id)
    assert fetched == user


def test_create_and_get_device(db: Path) -> None:
    store.create_user(db, display_name="mark")
    device = store.create_device(db, hostname="mbp", label="work")
    fetched = store.get_device(db, device.id)
    assert fetched.hostname == "mbp"
    assert fetched.label == "work"


def test_upsert_project_dedupes(db: Path) -> None:
    store.upsert_project(db, "whydatapp")
    store.upsert_project(db, "whydatapp")
    assert store.list_projects(db) == ["whydatapp"]



def _make_install(db: Path, **overrides) -> Install:
    user = store.get_solo_user(db) or store.create_user(db, display_name="t")
    device = store.get_solo_device(db) or store.create_device(db, hostname="h")
    payload = dict(
        command="brew install ripgrep",
        package_name="ripgrep",
        manager="brew",
        install_dir="/tmp",
        resolved_path=None,
        exit_code=0,
        user_id=user.id,
        device_id=device.id,
    )
    payload.update(overrides)
    return store.create_install(db, **payload)


def test_create_install_assigns_sync_id_and_timestamps(db: Path) -> None:
    inst = _make_install(db)
    assert inst.sync_id
    assert inst.installed_at
    assert inst.updated_at
    assert inst.metadata_complete == 0


def test_update_install_metadata(db: Path) -> None:
    inst = _make_install(db)
    updated = store.update_install(
        db,
        inst.id,
        display_name="ripgrep",
        what_it_does="fast grep",
        project="whydatapp",
        why="speed",
        disposition="doc",
        metadata_complete=1,
    )
    assert updated.disposition == "doc"
    assert updated.metadata_complete == 1
    assert updated.updated_at >= inst.updated_at


def test_list_installs_filters(db: Path) -> None:
    _make_install(db, command="brew install a", package_name="a")
    _make_install(db, command="npm i -g b", package_name="b", manager="npm")
    installs = store.list_installs(db, InstallFilters(manager="brew"))
    assert len(installs) == 1
    assert installs[0].package_name == "a"


def test_search_installs_uses_fts(db: Path) -> None:
    inst = _make_install(db)
    store.update_install(db, inst.id, why="needed for code search")
    results = store.search_installs(db, "code")
    assert len(results) == 1
    assert results[0].id == inst.id


def test_soft_delete_install(db: Path) -> None:
    inst = _make_install(db)
    store.soft_delete_install(db, inst.id)
    assert store.list_installs(db, InstallFilters()) == []
    assert store.list_installs(db, InstallFilters(include_deleted=True))[0].deleted == 1


def test_recent_duplicate_detection(db: Path) -> None:
    _make_install(db)
    assert store.recent_duplicate_exists(
        db, command="brew install ripgrep", install_dir="/tmp", within_seconds=60
    )
    assert not store.recent_duplicate_exists(
        db, command="brew install ripgrep", install_dir="/elsewhere", within_seconds=60
    )


def test_find_existing_install_returns_most_recent(db: Path) -> None:
    # Create two installs for the same package; should return the most recent.
    _make_install(db, installed_at="2026-01-01T00:00:00+00:00")
    inst2 = _make_install(
        db,
        command="brew install ripgrep",
        package_name="ripgrep",
        manager="brew",
        installed_at="2026-02-01T00:00:00+00:00",
    )
    found = store.find_existing_install(db, manager="brew", package_name="ripgrep")
    assert found is not None
    assert found.id == inst2.id


def test_find_existing_install_skips_deleted(db: Path) -> None:
    inst = _make_install(db)
    store.soft_delete_install(db, inst.id)
    found = store.find_existing_install(db, manager="brew", package_name="ripgrep")
    assert found is None


def test_record_reinstall_bumps_counter(db: Path) -> None:
    inst = _make_install(db)
    assert inst.reinstall_count == 0
    assert inst.last_installed_at is None

    updated = store.record_reinstall(db, inst.id)
    assert updated.reinstall_count == 1
    assert updated.last_installed_at is not None

    updated2 = store.record_reinstall(db, inst.id)
    assert updated2.reinstall_count == 2
