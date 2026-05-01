from __future__ import annotations

from pathlib import Path
from typing import Any

from why import store
from why.bootstrap import ensure_ready
from why.config import load_presentation


def get_db() -> Path:
    return ensure_ready()


def get_presentation() -> dict[str, Any]:
    return load_presentation()


def get_purposes(db: Path = None) -> list[store.Purpose]:  # type: ignore[assignment]
    """FastAPI dependency — returns purposes from DB, falling back to empty list."""
    if db is None:
        db = get_db()
    return store.list_purposes(db)
