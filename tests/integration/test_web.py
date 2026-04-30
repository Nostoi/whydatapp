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
