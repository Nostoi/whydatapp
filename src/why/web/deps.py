from __future__ import annotations

from pathlib import Path
from typing import Any

from why.bootstrap import ensure_ready
from why.config import load_presentation


def get_db() -> Path:
    return ensure_ready()


def get_presentation() -> dict[str, Any]:
    return load_presentation()
