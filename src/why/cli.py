from __future__ import annotations

import json
import os
import sys
from pathlib import Path as _P

import click
import typer
from rich.console import Console
from rich.table import Table

from why import __version__, store
from why.bootstrap import ensure_ready
from why.capture import capture
from why.detect import match_install
from why.markdown import to_markdown
from why.prompts import run_metadata_prompt
from why.store import InstallFilters


class WhyGroup(typer.core.TyperGroup):
    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if not args and self.no_args_is_help and not ctx.resilient_parsing:
            click.echo(ctx.get_help(), color=ctx.color)
            ctx.exit()
        return super().parse_args(ctx, args)


app = typer.Typer(
    add_completion=False,
    cls=WhyGroup,
    invoke_without_command=True,
    no_args_is_help=True,
    help="Track why you installed every tool.",
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"why {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True, no_args_is_help=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True),
) -> None:
    """why?"""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


@app.command("list")
def list_cmd(
    disposition: str | None = typer.Option(
        None, "--purpose", help="Filter by purpose (doc, setup, experimental, remove, ignore)."
    ),
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
    for col in ("id", "name", "manager", "project", "purpose", "installed_at", "run from"):
        t.add_column(col)
    for r in rows:
        # Format installed_at as YYYY-MM-DD HH:MM
        ts = r.installed_at
        if len(ts) >= 16:
            ts = ts[:10] + " " + ts[11:16]
        t.add_row(
            str(r.id),
            r.display_name or r.package_name or "",
            r.manager,
            r.project or "",
            r.disposition or "—",
            ts,
            r.install_dir,
        )
    console.print(t)


@app.command("log")
def log_cmd(
    cmd: list[str] = typer.Argument(..., help="The install command, after `--`."),  # noqa: B008
    cwd: str = typer.Option(None, help="Override cwd; defaults to current directory."),
    enrich: bool = typer.Option(
        False,
        "--enrich",
        help="When set, behave like the hook: update an existing complete entry instead of "
             "creating a new one. Useful if you want enrichment from a manual `why log`.",
    ),
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

    capture(
        db,
        command_str=command_str,
        work_dir=work_dir,
        enrich=enrich,
        console=console,
        input=sys.stdin,
        output=sys.stdout,
    )


@app.command("review")
def review_cmd() -> None:
    """Drain the skipped/incomplete queue, one entry at a time."""
    db = ensure_ready()
    pending = store.list_skipped(db)
    if not pending:
        console.print("Review queue is empty.")
        return
    for inst in pending:
        result = run_metadata_prompt(
            default_name=inst.display_name or inst.package_name,
            default_project=inst.project,
            command=inst.command,
            cwd=inst.install_dir,
            input=sys.stdin,
            output=sys.stdout,
        )
        if result.disposition == "skip":
            console.print(f"  [dim]still skipped (id={inst.id})[/dim]")
            continue
        if result.project:
            store.upsert_project(db, result.project)
        store.update_install(
            db, inst.id,
            display_name=result.display_name,
            what_it_does=result.what_it_does,
            project=result.project,
            why=result.why,
            notes=result.notes,
            disposition=result.disposition,
            metadata_complete=1 if result.metadata_complete else 0,
        )
        console.print(f"  [green]✓[/green] reviewed (id={inst.id}).")


@app.command("export")
def export_cmd(
    fmt: str = typer.Option("md", "--format"),
    out: _P = typer.Option(..., "--out"),  # noqa: B008
    disposition: str | None = typer.Option(None, "--purpose", help="Filter by purpose key."),
    project: str | None = typer.Option(None),
) -> None:
    """Export installs to a file (md|json)."""
    db = ensure_ready()
    rows = store.list_installs(
        db,
        InstallFilters(disposition=disposition, project=project, limit=10_000),
    )
    if fmt == "md":
        out.write_text("\n".join(to_markdown(r) for r in rows))
    elif fmt == "json":
        out.write_text(json.dumps([r.__dict__ for r in rows], indent=2, default=str))
    else:
        console.print("[red]format must be md or json[/red]")
        raise typer.Exit(code=2)
    console.print(f"wrote {len(rows)} entries → {out}")


@app.command("delete")
def delete_cmd(
    install_id: int,
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation."),
) -> None:
    """Soft-delete an install by id."""
    db = ensure_ready()
    inst = store.get_install(db, install_id)
    if not inst:
        console.print(f"[red]no install with id={install_id}[/red]")
        raise typer.Exit(code=1)
    if not yes:
        ok = typer.confirm(f"Delete '{inst.display_name or inst.package_name}'?")
        if not ok:
            raise typer.Exit(code=0)
    store.soft_delete_install(db, install_id)
    console.print(f"[green]✓[/green] deleted (soft) id={install_id}.")


def _primary_lan_ip() -> str | None:
    """Best-effort: the local IP that would be used to reach the public internet.
    No packet is actually sent; we just ask the kernel which interface it would route to."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip: str = s.getsockname()[0]
            return ip
        finally:
            s.close()
    except OSError:
        return None


def _serve_urls(host: str, port: int) -> tuple[str, list[str]]:
    """Return (browser_url, [printed_urls]) for the given bind host."""
    if host in ("0.0.0.0", "::", ""):
        urls = [f"http://127.0.0.1:{port}/"]
        lan = _primary_lan_ip()
        if lan and lan != "127.0.0.1":
            urls.append(f"http://{lan}:{port}/  (LAN)")
        return urls[0], urls
    return f"http://{host}:{port}/", [f"http://{host}:{port}/"]


@app.command("serve")
def serve_cmd(
    host: str | None = typer.Option(
        None, help="Bind host. Default 127.0.0.1 (localhost only). Use 0.0.0.0 for LAN."
    ),
    port: int | None = typer.Option(None, help="Bind port. Default 7873."),
    open_browser: bool = typer.Option(True, "--open/--no-open"),
    lan: bool = typer.Option(
        False, "--lan", help="Shortcut for --host 0.0.0.0 (exposes to your local network)."
    ),
) -> None:
    """Start the local web UI."""
    import webbrowser

    import uvicorn

    from why.config import load_config
    from why.web.app import create_app

    cfg = load_config()
    h = "0.0.0.0" if lan else (host or cfg["web"]["host"])
    p = port or int(cfg["web"]["port"])

    browser_url, printed = _serve_urls(h, p)
    console.print(f"[bold]whydatApp[/bold] [dim]v{__version__}[/dim] — web UI starting…")
    for url in printed:
        console.print(f"  → {url}")
    if h in ("0.0.0.0", "::", ""):
        console.print(
            "  [yellow]exposed to LAN[/yellow] — anyone on your network can reach this. "
            "Press Ctrl-C to stop."
        )
    else:
        console.print("  [dim]localhost only · press Ctrl-C to stop[/dim]")

    if open_browser:
        webbrowser.open(browser_url)
    uvicorn.run(create_app(), host=h, port=p, log_level="warning")


@app.command("init")
def init_cmd() -> None:
    """First-run interactive setup wizard."""
    from why.init_wizard import run_wizard
    rc_code = run_wizard(console)
    raise typer.Exit(code=rc_code)


@app.command("uninstall")
def uninstall_cmd() -> None:
    """Remove the shell hook and (optionally) the ~/.why directory."""
    import shutil
    import sys

    from why.paths import why_home as _wh
    from why.shells.installer import detect_shell, rc_file_for, remove_from_rc

    shell = detect_shell()
    rc = rc_file_for(shell)
    remove_from_rc(rc)
    console.print(f"[green]✓[/green] removed hook block from {rc}")

    if sys.platform == "darwin":
        from why.autostart import uninstall_macos_launchd
        uninstall_macos_launchd()
    elif sys.platform.startswith("linux"):
        from why.autostart import uninstall_linux_systemd
        uninstall_linux_systemd()

    home = _wh()
    if typer.confirm(
        f"Also delete data directory {home}? This wipes your install history.",
        default=False,
    ):
        if home.exists():
            shutil.rmtree(home)
        console.print(f"[green]✓[/green] removed {home}")
    else:
        console.print(f"  [dim]kept {home}[/dim]")


@app.command("_hook", hidden=True)
def hook_cmd(
    cmd: str = typer.Option(...),
    cwd: str = typer.Option(...),
    code: int = typer.Option(...),
) -> None:
    """Internal: invoked by the shell hook. Always exits 0."""
    from why.hook_runner import run_hook
    rc = run_hook(command=cmd, cwd=cwd, exit_code=code)
    raise typer.Exit(code=rc)
