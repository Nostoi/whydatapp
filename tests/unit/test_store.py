from __future__ import annotations

from pathlib import Path

import pytest

from why import store
from why.schema import migrate


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
    user = store.create_user(db, display_name="mark")
    device = store.create_device(db, hostname="mbp", label="work")
    fetched = store.get_device(db, device.id)
    assert fetched.hostname == "mbp"
    assert fetched.label == "work"


def test_upsert_project_dedupes(db: Path) -> None:
    store.upsert_project(db, "whydatapp")
    store.upsert_project(db, "whydatapp")
    assert store.list_projects(db) == ["whydatapp"]
