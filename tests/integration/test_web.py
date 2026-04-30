from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from why import store
from why.bootstrap import ensure_ready
from why.web.app import create_app
from why.web.templates_env import make_env


def _client(why_home: Path) -> TestClient:
    ensure_ready()
    c = TestClient(create_app())
    c.get("/installs")  # prime CSRF cookie
    return c


def test_root_redirects_to_installs(why_home: Path) -> None:
    c = _client(why_home)
    r = c.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"].endswith("/installs")


def test_installs_page_renders(why_home: Path) -> None:
    c = _client(why_home)
    r = c.get("/installs")
    assert r.status_code == 200
    assert "whydatApp" in r.text
    assert "localhost · no network" in r.text


def test_static_css_served(why_home: Path) -> None:
    c = _client(why_home)
    r = c.get("/static/css/tailwind.css")
    assert r.status_code == 200


def test_pill_partial_renders():
    env = make_env()
    html = env.get_template("components/pill.html").render(label="Doc", color="#2563eb")
    assert "Doc" in html
    assert "#2563eb" in html


def test_manager_badge_falls_back_when_unknown():
    env = make_env()
    html = env.get_template("components/manager_badge.html").render(manager="custom", pres={})
    assert "custom" in html
    assert "📦" in html


def test_manager_badge_does_not_render_raw_html(why_home: Path) -> None:
    _seed_one(why_home)
    c = _client(why_home)
    r = c.get("/installs")
    assert r.status_code == 200
    # The bug: when the label was pre-built as HTML and passed to the pill,
    # autoescape would emit e.g. &lt;span class="mr-1"&gt;🍺&lt;/span&gt;Homebrew
    # as visible text. Confirm no escaped HTML tags appear.
    assert '&lt;span' not in r.text
    # The icon span is correctly emitted as real HTML markup — check it renders
    assert '<span class="mr-1">🍺</span>' in r.text


def _seed_one(why_home: Path) -> int:
    db = ensure_ready()
    user = store.get_solo_user(db)
    device = store.get_solo_device(db)
    inst = store.create_install(
        db, user_id=user.id, device_id=device.id,
        command="brew install ripgrep", package_name="ripgrep", manager="brew",
        install_dir="/tmp", resolved_path=None, exit_code=0,
    )
    store.update_install(db, inst.id, display_name="ripgrep", disposition="doc",
                         what_it_does="fast grep", project="p", why="speed",
                         metadata_complete=1)
    return inst.id


def test_table_lists_installs(why_home: Path) -> None:
    _seed_one(why_home)
    c = _client(why_home)
    r = c.get("/installs")
    assert r.status_code == 200
    assert "ripgrep" in r.text


def test_table_fragment_endpoint(why_home: Path) -> None:
    _seed_one(why_home)
    c = _client(why_home)
    r = c.get("/installs/table?manager=brew")
    assert r.status_code == 200
    assert "ripgrep" in r.text
    assert "<header" not in r.text


def test_filter_excludes_other_managers(why_home: Path) -> None:
    _seed_one(why_home)
    c = _client(why_home)
    r = c.get("/installs/table?manager=npm")
    assert "ripgrep" not in r.text


def test_edit_panel_returned_for_row(why_home: Path) -> None:
    iid = _seed_one(why_home)
    c = _client(why_home)
    r = c.get(f"/installs/{iid}/edit")
    assert r.status_code == 200
    # Modal fragment: must have a form posting to the install URL
    assert f'action="/installs/{iid}"' not in r.text  # form uses hx-post, not action attr
    assert f'hx-post="/installs/{iid}"' in r.text
    # Must have a close button
    assert "edit-modal" in r.text and "close()" in r.text
    # Must have the fields
    assert "what does it do" in r.text.lower()


def test_post_updates_row(why_home: Path) -> None:
    iid = _seed_one(why_home)
    c = _client(why_home)
    r = c.post(
        f"/installs/{iid}",
        data={
            "display_name": "rg",
            "what_it_does": "ripgrep",
            "project": "p",
            "why": "speed v2",
            "disposition": "experimental",
            "notes": "",
            "metadata_complete": "1",
            "csrf_token": c.cookies.get("why_csrf", ""),
        },
    )
    assert r.status_code == 200
    # Response includes updated row markup
    assert "rg" in r.text
    # Response signals modal close
    assert "HX-Trigger" in r.headers
    assert "closeEditModal" in r.headers["HX-Trigger"]
    db = ensure_ready()
    inst = store.get_install(db, iid)
    assert inst.why == "speed v2"
    assert inst.disposition == "experimental"


def test_install_update_signals_modal_close(why_home: Path) -> None:
    iid = _seed_one(why_home)
    c = _client(why_home)
    c.get("/installs")  # prime CSRF cookie
    token = c.cookies.get("why_csrf")
    r = c.post(f"/installs/{iid}", data={
        "display_name": "rg", "what_it_does": "g", "project": "p",
        "why": "speed v3", "disposition": "doc", "notes": "",
        "metadata_complete": "1", "csrf_token": token,
    })
    assert r.status_code == 200
    assert "HX-Trigger" in r.headers
    assert "closeEditModal" in r.headers["HX-Trigger"]


def test_installs_page_has_edit_modal_skeleton(why_home: Path) -> None:
    c = _client(why_home)
    r = c.get("/installs")
    assert r.status_code == 200
    assert 'id="edit-modal"' in r.text
    assert "<dialog" in r.text


def test_share_returns_markdown(why_home: Path) -> None:
    iid = _seed_one(why_home)
    c = _client(why_home)
    r = c.post(
        f"/installs/{iid}/share",
        headers={"X-CSRF-Token": c.cookies.get("why_csrf", "")},
    )
    assert r.status_code == 200
    assert "**ripgrep**" in r.text


def test_export_md(why_home: Path) -> None:
    iid = _seed_one(why_home)
    c = _client(why_home)
    r = c.get(f"/export?ids={iid}&format=md")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    assert "ripgrep" in r.text


def test_export_json(why_home: Path) -> None:
    iid = _seed_one(why_home)
    c = _client(why_home)
    r = c.get(f"/export?ids={iid}&format=json")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert "ripgrep" in r.text


def test_dashboard_renders(why_home: Path) -> None:
    _seed_one(why_home)
    c = _client(why_home)
    r = c.get("/dashboard")
    assert r.status_code == 200
    assert "By disposition" in r.text or "Disposition" in r.text
    assert "By manager" in r.text or "Manager" in r.text
    assert "Stale review" in r.text


def test_stale_review_shows_skipped(why_home: Path) -> None:
    db = ensure_ready()
    user = store.get_solo_user(db)
    device = store.get_solo_device(db)
    store.create_install(
        db, user_id=user.id, device_id=device.id,
        command="brew install fd", package_name="fd", manager="brew",
        install_dir="/tmp", resolved_path=None, exit_code=0,
    )
    c = _client(why_home)
    r = c.get("/dashboard")
    assert "fd" in r.text


def test_review_redirects_when_empty(why_home: Path) -> None:
    c = _client(why_home)
    r = c.get("/review", follow_redirects=False)
    assert r.status_code in (200, 307)


def test_review_shows_first_pending(why_home: Path) -> None:
    db = ensure_ready()
    user = store.get_solo_user(db)
    device = store.get_solo_device(db)
    store.create_install(
        db, user_id=user.id, device_id=device.id,
        command="brew install fd", package_name="fd", manager="brew",
        install_dir="/tmp", resolved_path=None, exit_code=0,
    )
    c = _client(why_home)
    r = c.get("/review")
    assert r.status_code == 200
    assert "fd" in r.text
    assert "Disposition" in r.text


def test_review_post_saves_and_advances(why_home: Path) -> None:
    db = ensure_ready()
    user = store.get_solo_user(db)
    device = store.get_solo_device(db)
    inst = store.create_install(
        db, user_id=user.id, device_id=device.id,
        command="brew install fd", package_name="fd", manager="brew",
        install_dir="/tmp", resolved_path=None, exit_code=0,
    )
    c = _client(why_home)
    r = c.post(
        f"/review/{inst.id}",
        data={
            "display_name": "fd", "what_it_does": "find replacement",
            "project": "p", "why": "speed",
            "disposition": "doc", "notes": "",
            "csrf_token": c.cookies.get("why_csrf", ""),
        },
        follow_redirects=False,
    )
    assert r.status_code in (200, 303)
    db = ensure_ready()
    inst = store.get_install(db, inst.id)
    assert inst.disposition == "doc"
    assert inst.metadata_complete == 1


def test_post_without_csrf_rejected(why_home: Path) -> None:
    iid = _seed_one(why_home)
    raw = TestClient(create_app(), raise_server_exceptions=False)
    r = raw.post(f"/installs/{iid}", data={"display_name": "x"})
    assert r.status_code == 403


def test_post_with_csrf_accepted(why_home: Path) -> None:
    iid = _seed_one(why_home)
    c = _client(why_home)
    c.get("/installs")
    token = c.cookies.get("why_csrf")
    assert token
    r = c.post(
        f"/installs/{iid}",
        data={
            "display_name": "rg", "what_it_does": "g",
            "project": "p", "why": "w",
            "disposition": "doc", "notes": "",
            "metadata_complete": "1",
            "csrf_token": token,
        },
    )
    assert r.status_code == 200


# ── Bulk endpoint tests ────────────────────────────────────────────────────────

def test_bulk_update_disposition(why_home: Path) -> None:
    """POST /installs/bulk changes disposition for all selected IDs."""
    db = ensure_ready()
    user = store.get_solo_user(db)
    device = store.get_solo_device(db)
    inst1 = store.create_install(
        db, user_id=user.id, device_id=device.id,
        command="brew install bat", package_name="bat", manager="brew",
        install_dir="/tmp", resolved_path=None, exit_code=0,
    )
    inst2 = store.create_install(
        db, user_id=user.id, device_id=device.id,
        command="brew install eza", package_name="eza", manager="brew",
        install_dir="/tmp", resolved_path=None, exit_code=0,
    )
    c = _client(why_home)
    token = c.cookies.get("why_csrf", "")
    r = c.post(
        "/installs/bulk",
        data={
            "selected": [str(inst1.id), str(inst2.id)],
            "disposition": "setup",
            "csrf_token": token,
        },
    )
    assert r.status_code == 200
    # Verify both rows updated in DB
    assert store.get_install(db, inst1.id).disposition == "setup"
    assert store.get_install(db, inst2.id).disposition == "setup"


def test_bulk_delete(why_home: Path) -> None:
    """POST /installs/bulk/delete soft-deletes all selected IDs."""
    db = ensure_ready()
    user = store.get_solo_user(db)
    device = store.get_solo_device(db)
    inst = store.create_install(
        db, user_id=user.id, device_id=device.id,
        command="brew install delta", package_name="delta", manager="brew",
        install_dir="/tmp", resolved_path=None, exit_code=0,
    )
    c = _client(why_home)
    token = c.cookies.get("why_csrf", "")
    r = c.post(
        "/installs/bulk/delete",
        data={"selected": [str(inst.id)], "csrf_token": token},
    )
    assert r.status_code == 200
    # Row still exists but is soft-deleted
    deleted = store.get_install(db, inst.id)
    assert deleted is not None
    assert deleted.deleted == 1
    # Deleted row should not appear in normal list
    rows = store.list_installs(db, store.InstallFilters())
    assert not any(row.id == inst.id for row in rows)


def test_bulk_update_empty_selection_is_noop(why_home: Path) -> None:
    """POST /installs/bulk with no IDs returns table without error."""
    c = _client(why_home)
    token = c.cookies.get("why_csrf", "")
    r = c.post(
        "/installs/bulk",
        data={"disposition": "setup", "csrf_token": token},
    )
    assert r.status_code == 200
