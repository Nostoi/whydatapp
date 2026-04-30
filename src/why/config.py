from __future__ import annotations

import tomllib
from importlib import resources
from typing import Any

import tomli_w

from why.paths import config_path, ensure_home, why_home


DEFAULT_CONFIG: dict[str, Any] = {
    "device": {"id": "", "label": ""},
    "user":   {"id": "", "display_name": "", "email": ""},
    "managers": {
        "brew": True, "npm": True, "pnpm": True, "yarn": True, "bun": True,
        "pip": True, "pipx": True, "uv": True, "cargo": True, "git": True,
        "gem": False, "go": False, "apt": False, "mas": False,
        "vscode": False, "docker": False,
    },
    "web": {"host": "127.0.0.1", "port": 7873, "autostart": False},
    "ui": {},
    "sync": {"enabled": False},
}


def load_config() -> dict[str, Any]:
    p = config_path("config")
    if not p.exists():
        return _deep_copy(DEFAULT_CONFIG)
    with p.open("rb") as f:
        cfg = tomllib.load(f)
    return _merge(_deep_copy(DEFAULT_CONFIG), cfg)


def write_config(cfg: dict[str, Any]) -> None:
    ensure_home()
    p = config_path("config")
    with p.open("wb") as f:
        tomli_w.dump(cfg, f)


def _default_presentation() -> dict[str, Any]:
    text = resources.files("why").joinpath("presentation.toml").read_text()
    return tomllib.loads(text)


def load_presentation() -> dict[str, Any]:
    base = _default_presentation()
    user = config_path("presentation")
    if user.exists():
        with user.open("rb") as f:
            override = tomllib.load(f)
        return _merge(base, override)
    return base


def load_user_ignore_patterns() -> tuple[str, ...]:
    p = why_home() / "ignore.toml"
    if not p.exists():
        return ()
    with p.open("rb") as f:
        data = tomllib.load(f)
    return tuple(data.get("patterns", ()))


def load_custom_patterns() -> list[dict[str, Any]]:
    p = why_home() / "patterns.toml"
    if not p.exists():
        return []
    with p.open("rb") as f:
        data = tomllib.load(f)
    return list(data.get("pattern", []))


def _deep_copy(d: dict[str, Any]) -> dict[str, Any]:
    return {k: (_deep_copy(v) if isinstance(v, dict) else v) for k, v in d.items()}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = _deep_copy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out
