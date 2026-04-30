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


import os
import sys

from why.detect import match_install
from why.project_infer import infer_project
from why.prompts import run_metadata_prompt
from why.resolve import resolve_path


@app.command("log")
def log_cmd(
    cmd: list[str] = typer.Argument(..., help="The install command, after `--`."),
    cwd: str = typer.Option(None, help="Override cwd; defaults to current directory."),
) -> None:
    """Log an install interactively. Used by the shell hook and for manual entries."""
    db = ensure_ready()
    command_str = " ".join(cmd)
    work_dir = cwd or os.getcwd()

    match = match_install(command_str)
    if match is None:
        console.print(
            f"[yellow]not recognized as an install: {command_str}[/yellow]"
        )
        raise typer.Exit(code=2)

    if store.recent_duplicate_exists(
        db, command=command_str, install_dir=work_dir, within_seconds=60
    ):
        console.print("[dim]recent duplicate; skipping.[/dim]")
        raise typer.Exit(code=0)

    user = store.get_solo_user(db)
    device = store.get_solo_device(db)
    assert user is not None and device is not None

    primary_pkg = match.packages[0]
    resolved = resolve_path(manager=match.manager, package=primary_pkg, cwd=work_dir)

    inst = store.create_install(
        db,
        user_id=user.id,
        device_id=device.id,
        command=command_str,
        package_name=primary_pkg,
        manager=match.manager,
        install_dir=work_dir,
        resolved_path=resolved,
        exit_code=0,
    )

    inferred_project = infer_project(work_dir)
    result = run_metadata_prompt(
        default_name=primary_pkg,
        default_project=inferred_project,
        command=command_str,
        cwd=work_dir,
        input=sys.stdin,
        output=sys.stdout,
    )

    if result.disposition == "skip":
        console.print(
            f"  [dim]skipped — review later via `why review` (id={inst.id})[/dim]"
        )
        return

    if result.project:
        store.upsert_project(db, result.project)

    store.update_install(
        db,
        inst.id,
        display_name=result.display_name,
        what_it_does=result.what_it_does,
        project=result.project,
        why=result.why,
        notes=result.notes,
        disposition=result.disposition,
        metadata_complete=1 if result.metadata_complete else 0,
    )
    console.print(f"  [green]✓[/green] logged (id={inst.id}).")
