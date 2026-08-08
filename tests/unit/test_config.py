from __future__ import annotations

from pathlib import Path

from why.config import (
    DEFAULT_CONFIG,
    load_config,
    load_custom_patterns,
    load_llm_ignore_patterns,
    load_presentation,
    load_user_ignore_patterns,
    write_config,
)


def test_load_config_returns_defaults_when_missing(why_home: Path) -> None:
    cfg = load_config()
    assert cfg["managers"]["brew"] is True
    assert cfg["web"]["port"] == 7873
    assert cfg["journal"]["max_commands"] == 500
    assert cfg["llm"]["enabled"] is False
    assert cfg["llm"]["provider"] == "openai-compatible"
    assert cfg["llm"]["confirm_before_send"] == "remote"


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


def test_llm_ignore_patterns_empty_when_missing(why_home: Path) -> None:
    assert load_llm_ignore_patterns() == ()


def test_llm_ignore_patterns_loads(why_home: Path) -> None:
    (why_home / "llm-ignore.toml").write_text('patterns = ["secret-project", "aws"]\n')
    assert load_llm_ignore_patterns() == ("secret-project", "aws")


def test_custom_patterns_empty_when_missing(why_home: Path) -> None:
    assert load_custom_patterns() == []


def test_write_config_preserves_file_when_nothing_changed(why_home: Path) -> None:
    """ensure_ready() rewrites config on every CLI call, and the hook now runs it on
    every prompt. An unconditional rewrite strips the user's comments within one
    prompt of installing, permanently, because tomli_w cannot preserve them.
    """
    from why.config import load_config, write_config

    p = why_home / "config.toml"
    p.write_text("# my hand-written comment\n[journal]\nmax_commands = 42\n")
    before = p.read_text()

    write_config(load_config())

    assert p.read_text() == before, "write_config rewrote a config that had not changed"


def test_write_config_still_persists_real_changes(why_home: Path) -> None:
    from why.config import load_config, write_config

    cfg = load_config()
    cfg["journal"]["max_commands"] = 99
    write_config(cfg)

    assert load_config()["journal"]["max_commands"] == 99
