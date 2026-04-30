from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def why_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate ~/.why per test by setting WHY_HOME to a tmp dir."""
    home = tmp_path / "why"
    home.mkdir()
    monkeypatch.setenv("WHY_HOME", str(home))
    return home
