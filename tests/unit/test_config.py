from __future__ import annotations

from pathlib import Path

from why.config import (
    DEFAULT_CONFIG,
    load_config,
    load_custom_patterns,
    load_presentation,
    load_user_ignore_patterns,
    write_config,
)


def test_load_config_returns_defaults_when_missing(why_home: Path) -> None:
    cfg = load_config()
    assert cfg["managers"]["brew"] is True
    assert cfg["web"]["port"] == 7873


def test_round_trip_config(why_home: Path) -> None:
    cfg = DEFAULT_CONFIG.copy()
    cfg["device"] = {"id": "abc", "label": "x"}
    write_config(cfg)
    loaded = load_config()
    assert loaded["device"]["label"] == "x"


def test_presentation_includes_brew(why_home: Path) -> None:
    p = load_presentation()
    assert p["brew"]["icon"]
    assert p["brew"]["color"].startswith("#")


def test_presentation_user_override(why_home: Path) -> None:
    (why_home / "presentation.toml").write_text(
        '[brew]\nicon = "X"\ncolor = "#000000"\nlabel = "Brew"\n'
    )
    p = load_presentation()
    assert p["brew"]["icon"] == "X"
    assert p["npm"]["label"] == "npm"


def test_user_ignore_patterns_empty_when_missing(why_home: Path) -> None:
    assert load_user_ignore_patterns() == ()


def test_user_ignore_patterns_loads(why_home: Path) -> None:
    (why_home / "ignore.toml").write_text('patterns = ["^foo", "^bar"]\n')
    assert load_user_ignore_patterns() == ("^foo", "^bar")


def test_custom_patterns_empty_when_missing(why_home: Path) -> None:
    assert load_custom_patterns() == []
