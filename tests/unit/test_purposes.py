from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from why import store
from why.bootstrap import ensure_ready
from why.web.app import create_app


def _client(why_home: Path) -> TestClient:
    ensure_ready()
    return TestClient(create_app())


# ---------------------------------------------------------------------------
# store CRUD
# ---------------------------------------------------------------------------

def test_list_purposes_returns_seed_data(why_home: Path) -> None:
    db = ensure_ready()
    purposes = store.list_purposes(db)
    keys = [p.key for p in purposes]
    assert "doc" in keys
    assert "setup" in keys
    assert "experimental" in keys
    assert "remove" in keys
    assert "ignore" in keys


def test_list_purposes_ordered_by_sort_order(why_home: Path) -> None:
    db = ensure_ready()
    purposes = store.list_purposes(db)
    orders = [p.sort_order for p in purposes]
    assert orders == sorted(orders)


def test_get_purpose_returns_correct(why_home: Path) -> None:
    db = ensure_ready()
    p = store.get_purpose(db, "doc")
    assert p is not None
    assert p.label == "Reference"
    assert p.built_in is True


def test_get_purpose_missing_returns_none(why_home: Path) -> None:
    db = ensure_ready()
    assert store.get_purpose(db, "nonexistent") is None


def test_create_purpose(why_home: Path) -> None:
    db = ensure_ready()
    p = store.create_purpose(db, key="work", label="Work", color="#ff0000", sort_order=10)
    assert p.key == "work"
    assert p.label == "Work"
    assert p.built_in is False
    fetched = store.get_purpose(db, "work")
    assert fetched is not None
    assert fetched.label == "Work"


def test_update_purpose_label(why_home: Path) -> None:
    db = ensure_ready()
    updated = store.update_purpose(db, "doc", label="Docs")
    assert updated.label == "Docs"
    assert store.get_purpose(db, "doc").label == "Docs"  # type: ignore[union-attr]


def test_update_purpose_missing_raises(why_home: Path) -> None:
    db = ensure_ready()
    with pytest.raises(KeyError):
        store.update_purpose(db, "no_such_key", label="X")


def test_update_purpose_no_fields_raises(why_home: Path) -> None:
    db = ensure_ready()
    with pytest.raises(ValueError, match="no fields"):
        store.update_purpose(db, "doc")


def test_delete_custom_purpose(why_home: Path) -> None:
    db = ensure_ready()
    store.create_purpose(db, key="temp", label="Temp", sort_order=99)
    store.delete_purpose(db, "temp")
    assert store.get_purpose(db, "temp") is None


def test_delete_builtin_purpose_raises(why_home: Path) -> None:
    db = ensure_ready()
    with pytest.raises(ValueError, match="built-in"):
        store.delete_purpose(db, "doc")


def test_delete_missing_purpose_raises(why_home: Path) -> None:
    db = ensure_ready()
    with pytest.raises(KeyError):
        store.delete_purpose(db, "ghost")


# ---------------------------------------------------------------------------
# web settings routes
# ---------------------------------------------------------------------------

def _csrf(c: TestClient) -> str:
    """Prime the CSRF cookie and return the token."""
    c.get("/settings/purposes")
    return c.cookies.get("why_csrf", "")


def test_settings_purposes_page_renders(why_home: Path) -> None:
    c = _client(why_home)
    r = c.get("/settings/purposes")
    assert r.status_code == 200
    assert "Purpose categories" in r.text
    assert "Reference" in r.text


def test_settings_purposes_add(why_home: Path) -> None:
    c = _client(why_home)
    token = _csrf(c)
    r = c.post("/settings/purposes", data={
        "key": "work", "label": "Work", "color": "#aabbcc", "sort_order": "10",
        "csrf_token": token,
    })
    assert r.status_code == 200
    assert "Work" in r.text
    db = ensure_ready()
    assert store.get_purpose(db, "work") is not None


def test_settings_purposes_edit(why_home: Path) -> None:
    c = _client(why_home)
    token = _csrf(c)
    r = c.post("/settings/purposes/doc/edit", data={
        "label": "Docs", "color": "#2563eb", "sort_order": "1",
        "csrf_token": token,
    })
    assert r.status_code == 200
    db = ensure_ready()
    assert store.get_purpose(db, "doc").label == "Docs"  # type: ignore[union-attr]


def test_settings_purposes_delete_custom(why_home: Path) -> None:
    db = ensure_ready()
    store.create_purpose(db, key="temp2", label="Temp2", sort_order=99)
    c = _client(why_home)
    token = _csrf(c)
    r = c.post(
        "/settings/purposes/temp2/delete",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert store.get_purpose(db, "temp2") is None


def test_settings_purposes_delete_builtin_silently_ignored(why_home: Path) -> None:
    """Deleting a built-in purpose via web should not crash (delete route suppresses errors)."""
    c = _client(why_home)
    token = _csrf(c)
    r = c.post("/settings/purposes/doc/delete", data={"csrf_token": token}, follow_redirects=False)
    assert r.status_code in (302, 303)
    db = ensure_ready()
    assert store.get_purpose(db, "doc") is not None
