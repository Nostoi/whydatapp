from __future__ import annotations

import os
from pathlib import Path


def why_home() -> Path:
    override = os.environ.get("WHY_HOME")
    if override:
        return Path(override)
    return Path.home() / ".why"


def db_path() -> Path:
    return why_home() / "data.db"


def log_path(name: str) -> Path:
    return why_home() / f"{name}.log"


def config_path(name: str) -> Path:
    return why_home() / f"{name}.toml"


def ensure_home() -> Path:
    home = why_home()
    home.mkdir(parents=True, exist_ok=True)
    (home / "backups").mkdir(exist_ok=True)
    return home
