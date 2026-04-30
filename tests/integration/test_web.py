from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from why.bootstrap import ensure_ready
from why.web.app import create_app


def _client(why_home: Path) -> TestClient:
    ensure_ready()
    return TestClient(create_app())


def test_root_redirects_to_installs(why_home: Path) -> None:
    c = _client(why_home)
    r = c.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"].endswith("/installs")


def test_installs_page_renders(why_home: Path) -> None:
    c = _client(why_home)
    r = c.get("/installs")
    assert r.status_code == 200
    assert "why?" in r.text
    assert "localhost · no network" in r.text


def test_static_css_served(why_home: Path) -> None:
    c = _client(why_home)
    r = c.get("/static/css/tailwind.css")
    assert r.status_code == 200


from why.web.templates_env import make_env


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


from why import store


def _seed_one(why_home: Path) -> int:
    db = ensure_ready()
    user = store.get_solo_user(db); device = store.get_solo_device(db)
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
        },
    )
    assert r.status_code == 200
    db = ensure_ready()
    inst = store.get_install(db, iid)
    assert inst.why == "speed v2"
    assert inst.disposition == "experimental"


def test_share_returns_markdown(why_home: Path) -> None:
    iid = _seed_one(why_home)
    c = _client(why_home)
    r = c.post(f"/installs/{iid}/share")
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
    user = store.get_solo_user(db); device = store.get_solo_device(db)
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
    user = store.get_solo_user(db); device = store.get_solo_device(db)
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
    user = store.get_solo_user(db); device = store.get_solo_device(db)
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
        },
        follow_redirects=False,
    )
    assert r.status_code in (200, 303)
    db = ensure_ready()
    inst = store.get_install(db, inst.id)
    assert inst.disposition == "doc"
    assert inst.metadata_complete == 1
