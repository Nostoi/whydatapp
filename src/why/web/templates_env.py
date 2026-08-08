from __future__ import annotations

from importlib import resources
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _templates_dir() -> Path:
    return Path(str(resources.files("why.web").joinpath("templates")))


def _llm_enabled() -> bool:
    """Read lazily on each render so the footer reflects the current setting."""
    from why.config import load_config

    try:
        return bool(load_config()["llm"]["enabled"])
    except Exception:  # noqa: BLE001 - a broken config must not break rendering
        return False


def make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_templates_dir())),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # Available to every template extending base.html, so the footer's privacy
    # claim cannot drift from the actual LLM setting.
    env.globals["llm_enabled"] = _llm_enabled
    return env
