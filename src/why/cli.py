from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from why import __version__, store
from why.bootstrap import ensure_ready
from why.store import InstallFilters

app = typer.Typer(add_completion=False, help="Track why you installed every tool.")
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"why {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True),
) -> None:
    """why?"""


@app.command("list")
def list_cmd(
    disposition: str | None = typer.Option(None),
    project: str | None = typer.Option(None),
    manager: str | None = typer.Option(None),
    incomplete_only: bool = typer.Option(False, "--incomplete"),
    limit: int = typer.Option(50),
) -> None:
    """List installs as a table."""
    db = ensure_ready()
    rows = store.list_installs(
        db,
        InstallFilters(
            disposition=disposition,
            project=project,
            manager=manager,
            incomplete_only=incomplete_only,
            limit=limit,
        ),
    )
    if not rows:
        console.print("No installs.")
        return
    t = Table()
    for col in ("id", "name", "manager", "project", "disposition", "installed_at"):
        t.add_column(col)
    for r in rows:
        t.add_row(
            str(r.id),
            r.display_name or r.package_name or "",
            r.manager,
            r.project or "",
            r.disposition or "—",
            r.installed_at,
        )
    console.print(t)
