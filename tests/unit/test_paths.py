from __future__ import annotations

from pathlib import Path

import pytest

from why.paths import config_path, db_path, log_path


def test_why_home_uses_env_override(why_home: Path) -> None:
    assert why_home == why_home


def test_db_path_under_home(why_home: Path) -> None:
    assert db_path() == why_home / "data.db"


def test_log_paths_under_home(why_home: Path) -> None:
    assert log_path("hook") == why_home / "hook.log"
    assert log_path("web") == why_home / "web.log"


def test_config_path_under_home(why_home: Path) -> None:
    assert config_path("config") == why_home / "config.toml"
    assert config_path("presentation") == why_home / "presentation.toml"


def test_default_home_is_dotwhy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("WHY_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    from why import paths
    assert paths.why_home() == tmp_path / ".why"
