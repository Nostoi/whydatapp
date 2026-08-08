"""Guards on what the *shipped wheel* can rely on, as opposed to the dev env.

The dev env installs from `uv.lock`; users get whatever the resolver picks from
`pyproject.toml`. Those diverged badly enough once to ship a broken release, so
the constraints that only hold for real installs get asserted here.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "why"

_CLICK_IMPORT = re.compile(r"^\s*(?:import click\b|from click(?:\.\w+)* import)", re.MULTILINE)


def test_no_source_module_imports_top_level_click():
    """`import click` is a landmine: it works in dev and crashes for users.

    typer >= 0.27 vendors click as `typer._click` and dropped its dependency on the
    top-level package. A CLI-only install (`uv tool install why-cli`) therefore has
    no `click` at all, and every command died with ModuleNotFoundError. The `[web]`
    install survived only because uvicorn happens to pull click in — and there
    `typer.Abort` is no longer `click.Abort`, so `except click.Abort` silently
    stopped catching user aborts.

    Use typer's own re-exports (`typer.echo`, `typer.Abort`, `typer.Context`); they
    resolve correctly on both the pre- and post-vendoring layouts.
    """
    offenders = sorted(
        p.relative_to(SRC).as_posix()
        for p in SRC.rglob("*.py")
        if _CLICK_IMPORT.search(p.read_text())
    )
    assert offenders == [], (
        f"these modules import click directly: {offenders}. "
        "Use typer's re-exports instead — click is not a dependency of a CLI-only install."
    )


def test_click_is_not_a_declared_dependency():
    """If click ever becomes a real dependency, the test above must be revisited
    rather than silently satisfied by adding it to pyproject."""
    pyproject = (SRC.parents[1] / "pyproject.toml").read_text()
    deps_block = pyproject.split("dependencies = [", 1)[1].split("]", 1)[0]
    assert "click" not in deps_block
