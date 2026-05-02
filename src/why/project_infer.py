from __future__ import annotations

from pathlib import Path

_MARKERS = (".git", "pyproject.toml", "package.json", "Cargo.toml", "go.mod")


def infer_project(cwd: str) -> str | None:
    p = Path(cwd).resolve()
    home = Path.home().resolve()
    for ancestor in [p, *p.parents]:
        # Stop at home directory — never return the home dir itself as a project name.
        if ancestor == home:
            break
        for m in _MARKERS:
            if (ancestor / m).exists():
                return ancestor.name
    return None
