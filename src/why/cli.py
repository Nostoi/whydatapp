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
from why.config import load_config, load_custom_patterns, write_config
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
err_console = Console(stderr=True)

# Commands that must never emit the stale-hook notice:
#   _hook / _record — run inside the shell's precmd; printing corrupts the terminal.
#   init / uninstall — rewrite or remove the hook themselves, so a notice is noise.
_NO_HOOK_NOTICE = frozenset({"_hook", "_record", "init", "uninstall"})


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"why {__version__}")
        raise typer.Exit()


def _refresh_hooks_if_stale(subcommand: str | None) -> None:
    """Bring `~/.why/hook.*` up to date and tell the user, once.

    Deliberately not in `ensure_ready()`: that also runs from the web app and the
    init wizard, and sits on the per-prompt hot path via `why _record`. Here it
    only runs for user-facing commands.

    `WHY_SUPPRESS` is set by every hook-initiated invocation — including
    `why follow status`, which is not a hidden command — so it doubles as the
    "we are inside the prompt cycle, do not print" signal. Old hooks set it too,
    which is what makes this safe for the very users we're upgrading.
    """
    if subcommand in _NO_HOOK_NOTICE or os.environ.get("WHY_SUPPRESS"):
        return
    try:
        from why.paths import why_home
        from why.shells.installer import refresh_stale_hooks

        refreshed = refresh_stale_hooks(why_home())
    except Exception:  # noqa: BLE001 - an upgrade notice must never fail a command
        return
    for shell, old, new in refreshed:
        was = f"v{old}" if old is not None else "unversioned"
        err_console.print(
            f"[yellow]↻[/yellow] {shell} shell hook updated ({was} → v{new}). "
            "Restart your shell or run:\n    [bold]exec $SHELL -l[/bold]"
        )


@app.callback(invoke_without_command=True, no_args_is_help=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True),
) -> None:
    """why?"""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()
    _refresh_hooks_if_stale(ctx.invoked_subcommand)


@app.command("list")
def list_cmd(
    disposition: str | None = typer.Option(
        None, "--purpose", help="Filter by purpose (doc, setup, experimental, remove, ignore)."
    ),
    project: str | None = typer.Option(None),
    manager: str | None = typer.Option(None),
    incomplete_only: bool = typer.Option(
        False, "--incomplete", help="Show ONLY entries with incomplete metadata (the review queue)."
    ),
    show_incomplete: bool = typer.Option(
        False, "--show-incomplete", help="Include entries with incomplete metadata in the output."
    ),
    show_removed: bool = typer.Option(
        False, "--show-removed", help="Include uninstalled entries in the output."
    ),
    show_all: bool = typer.Option(
        False, "--all", "-a", help="Shorthand: include both incomplete and uninstalled entries.",
    ),
    limit: int = typer.Option(50),
) -> None:
    """List installs as a table.

    By default shows only currently-installed entries with complete metadata. Use
    --show-incomplete, --show-removed, or --all to broaden the view, or
    --incomplete to narrow it to the review queue.
    """
    if show_all:
        show_incomplete = True
        show_removed = True
    db = ensure_ready()
    rows = store.list_installs(
        db,
        InstallFilters(
            disposition=disposition,
            project=project,
            manager=manager,
            incomplete_only=incomplete_only,
            complete_only=not (incomplete_only or show_incomplete),
            show_removed=show_removed,
            limit=limit,
        ),
    )
    if not rows:
        console.print("No installs.")
        return
    t = Table()
    for col in (
        "id", "name", "status", "manager", "project", "purpose",
        "installed_at", "uninstalled_at", "run from",
    ):
        t.add_column(col, overflow="fold", no_wrap=False)
    for r in rows:
        ts = r.installed_at
        if len(ts) >= 16:
            ts = ts[:10] + " " + ts[11:16]
        if r.removed_at:
            status = "[red]uninstalled[/red]"
            removed_ts = r.removed_at[:10] + " " + r.removed_at[11:16]
        elif r.metadata_complete == 0:
            status = "[yellow]incomplete[/yellow]"
            removed_ts = "—"
        else:
            status = "[green]installed[/green]"
            removed_ts = "—"
        t.add_row(
            str(r.id),
            r.display_name or r.package_name or "",
            status,
            r.manager,
            r.project or "",
            r.disposition or "—",
            ts,
            removed_ts,
            r.install_dir,
        )
    # Render to a wide console so cells aren't truncated under non-TTY widths
    # (e.g. CI, CliRunner). When connected to a real TTY this still respects it.
    width = console.size.width if console.is_terminal else 200
    Console(width=width).print(t)


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

    match = match_install(command_str, custom_patterns=load_custom_patterns())
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
    from why.shells.installer import (
        SHELLS,
        detect_shell,
        hook_target_for,
        rc_file_for,
        remove_from_rc,
    )

    shell = detect_shell()
    rc = rc_file_for(shell)
    remove_from_rc(rc)
    console.print(f"[green]✓[/green] removed hook block from {rc}")

    # Remove the payload too, for every shell — not just $SHELL. Leaving it behind
    # would strand an orphan that the stale-hook auto-refresh then keeps updating,
    # nagging an uninstalled user to restart their shell on every version bump.
    home = _wh()
    for sh in SHELLS:
        target = hook_target_for(sh, home)
        if target.exists():
            target.unlink()
            console.print(f"[green]✓[/green] removed {target}")

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
    history: str = typer.Option("", help="Record-separator (\\x1e) delimited prior commands"),
) -> None:
    """Internal: invoked by the shell hook. Always exits 0."""
    from why.hook_runner import run_hook
    rc = run_hook(command=cmd, cwd=cwd, exit_code=code, raw_history=history)
    raise typer.Exit(code=rc)


@app.command("_record", hidden=True)
def record_cmd(
    cmd: str = typer.Option(...),
    cwd: str = typer.Option(...),
    code: int = typer.Option(...),
    shell: str | None = typer.Option(None),
) -> None:
    """Internal: record one shell command for follow/recall.

    Runs on every shell prompt, so it must never break the user's terminal:
    log and exit 0 on any failure, exactly like `why _hook`.
    """
    from why.paths import log_error
    from why.sessions import record_command_event

    try:
        db = ensure_ready()
        record_command_event(db, command=cmd, cwd=cwd, shell=shell, exit_code=code)
    except Exception as e:  # noqa: BLE001 - never fail the prompt
        log_error(f"record error: {e!r} cmd={cmd!r}")


@app.command("show")
def show_cmd(
    install_id: int = typer.Argument(..., help="Install ID (from why list)"),
) -> None:
    """Show full details and command history for an install."""
    db = ensure_ready()
    inst = store.get_install(db, install_id)
    if inst is None:
        console.print(f"[red]No install with id {install_id}[/red]")
        raise typer.Exit(1)
    if inst.removed_at:
        status = "[red]uninstalled[/red]"
    elif inst.metadata_complete == 0:
        status = "[yellow]incomplete[/yellow]"
    else:
        status = "[green]installed[/green]"
    console.print(f"[bold]#{inst.id}[/bold]  {inst.command}")
    console.print(f"  Status:    {status}")
    console.print(f"  Manager:   {inst.manager}")
    if inst.display_name:
        console.print(f"  Name:      {inst.display_name}")
    if inst.what_it_does:
        console.print(f"  Does:      {inst.what_it_does}")
    if inst.project:
        console.print(f"  Project:   {inst.project}")
    if inst.why:
        # After uninstall, the `why` field holds the removal reason.
        why_label = "Reason:    " if inst.removed_at else "Why:       "
        console.print(f"  {why_label}{inst.why}")
    if inst.notes:
        console.print(f"  Notes:     {inst.notes}")
    console.print(f"  Purpose:   {inst.disposition or '—'}")
    console.print(f"  Run from:  {inst.install_dir}")
    if inst.resolved_path:
        console.print(f"  Installed: {inst.resolved_path}")
    if inst.source_url:
        console.print(f"  Source:    {inst.source_url}")
    console.print(f"  Captured:  {inst.installed_at}")
    if inst.reinstall_count:
        last = inst.last_installed_at or inst.installed_at
        console.print(f"  Reinstalls: {inst.reinstall_count}  (last: {last})")
    if inst.removed_at:
        console.print(f"  Removed:   {inst.removed_at}")
    history = store.get_command_history(db, install_id)
    if history:
        console.print("\n  [dim]Commands before this install:[/dim]")
        for i, h in enumerate(history, 1):
            console.print(f"    {i:2}. {h}")


# ---------------------------------------------------------------------------
# follow / recall / sessions / llm
# ---------------------------------------------------------------------------

follow_app = typer.Typer(help="Record an intentional terminal task session.")
app.add_typer(follow_app, name="follow")


@follow_app.command("start")
def follow_start(
    title: str | None = typer.Option(None, "--title"),
    project: str | None = typer.Option(None, "--project"),
    shell: str | None = typer.Option(None, "--shell", help="Override detected shell."),
) -> None:
    from why.sessions import start_follow_session

    db = ensure_ready()
    try:
        session = start_follow_session(
            db,
            title=title,
            project=project,
            shell=shell or os.environ.get("SHELL", "").rsplit("/", 1)[-1] or None,
            cwd=os.getcwd(),
        )
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e
    console.print(f"[green]Recording session #{session.id}[/green]")


@follow_app.command("stop")
def follow_stop() -> None:
    from why.sessions import stop_follow_session

    db = ensure_ready()
    try:
        session = stop_follow_session(db, cwd=os.getcwd())
    except RuntimeError as e:
        console.print(f"[yellow]{e}[/yellow]")
        raise typer.Exit(1) from e
    name = session.title or "untitled"
    console.print(f"Saved session #{session.id}: {name}")
    console.print(f"View the transcript: why sessions show {session.id}")
    console.print(
        f"Send it to your configured LLM for a task recap: why sessions summarize {session.id}"
    )
    console.print(f"Mark it as not needing an LLM summary: why sessions ignore-llm {session.id}")


@follow_app.command("status")
def follow_status(
    porcelain: bool = typer.Option(False, "--porcelain", help="Print active/inactive only."),
) -> None:
    db = ensure_ready()
    active = store.get_active_task_session(db)
    if porcelain:
        console.print("active" if active else "inactive")
        return
    if active is None:
        console.print("No active follow session.")
    else:
        console.print(f"Recording session #{active.id}: {active.title or 'untitled'}")


@follow_app.command("cancel")
def follow_cancel() -> None:
    from why.sessions import cancel_follow_session

    db = ensure_ready()
    try:
        session = cancel_follow_session(db)
    except RuntimeError as e:
        console.print(f"[yellow]{e}[/yellow]")
        raise typer.Exit(1) from e
    console.print(f"Cancelled session #{session.id}.")


def _parse_selected_positions(selection: str, *, max_position: int) -> set[int]:
    from why.sessions import parse_selection

    return parse_selection(selection, max_position=max_position)


@app.command("recall")
def recall_cmd(
    last: int = typer.Option(30, "--last", min=1),
    interactive: bool = typer.Option(False, "--interactive"),
    title: str | None = typer.Option(None, "--title"),
) -> None:
    from why.sessions import create_recall_session

    db = ensure_ready()
    selected: set[int] | None = None
    if interactive:
        entries = list(reversed(store.list_recent_command_journal(db, limit=last)))
        if not entries:
            console.print("[yellow]No recent commands to recall.[/yellow]")
            raise typer.Exit(1)
        for index, entry in enumerate(entries, 1):
            console.print(f"{index:2}. [{entry.exit_code}] {entry.command}")
        try:
            selection = typer.prompt("Select commands")
        except (click.Abort, EOFError):
            # Non-TTY fallback (CLAUDE.md): save the whole window rather than
            # aborting. Detected by the failed read, not by isatty(), because
            # stdin is not a TTY even when input has been piped in.
            console.print("\n[yellow]No input available — saving all recent commands.[/yellow]")
            selection = ""
        if selection:
            try:
                selected = _parse_selected_positions(selection, max_position=len(entries))
            except ValueError as e:
                console.print(f"[red]{e}[/red]")
                raise typer.Exit(2) from e
    try:
        session = create_recall_session(db, limit=last, title=title, selected_positions=selected)
    except ValueError as e:
        console.print(f"[yellow]{e}[/yellow]")
        raise typer.Exit(1) from e
    console.print(f"Saved recall session #{session.id}: {session.title or 'untitled'}")
    console.print(f"View the transcript: why sessions show {session.id}")
    console.print(
        f"Send it to your configured LLM for a task recap: why sessions summarize {session.id}"
    )


sessions_app = typer.Typer(help="Browse and summarize task sessions.")
app.add_typer(sessions_app, name="sessions")


@sessions_app.command("list")
def sessions_list(
    summary_status: str | None = typer.Option(None, "--summary-status"),
    limit: int = typer.Option(100, "--limit"),
) -> None:
    db = ensure_ready()
    rows = store.list_task_sessions(db, summary_status=summary_status, limit=limit)
    if not rows:
        console.print("No sessions.")
        return
    t = Table()
    for col in ("id", "source", "status", "summary", "title", "started"):
        t.add_column(col, overflow="fold", no_wrap=False)
    for row in rows:
        t.add_row(
            str(row.id),
            row.source,
            row.status,
            row.summary_status,
            row.title or "",
            row.started_at[:16].replace("T", " "),
        )
    Console(width=console.size.width if console.is_terminal else 160).print(t)


@sessions_app.command("show")
def sessions_show(session_id: int) -> None:
    db = ensure_ready()
    session = store.get_task_session(db, session_id)
    if session is None:
        console.print(f"[red]No session with id {session_id}[/red]")
        raise typer.Exit(1)
    console.print(f"[bold]Session #{session.id}[/bold]  {session.title or 'untitled'}")
    console.print(f"  Source:    {session.source}")
    console.print(f"  Status:    {session.status}")
    console.print(f"  Summary:   {session.summary_status}")
    console.print(f"  Project:   {session.project or '—'}")
    console.print(f"  Started:   {session.started_at}")
    if session.ended_at:
        console.print(f"  Ended:     {session.ended_at}")
    console.print("\n  [dim]Transcript:[/dim]")
    for command in store.list_task_session_commands(db, session.id):
        code = "?" if command.exit_code is None else str(command.exit_code)
        console.print(f"    {command.position + 1:2}. [{code}] {command.command}")
        console.print(f"        cwd: {command.cwd}")
    summaries = store.list_task_session_summaries(db, session.id)
    if summaries:
        console.print("\n  [dim]Latest summary:[/dim]")
        console.print(summaries[0].summary_markdown)


def _known_installs_for_commands(
    db: _P, commands: list[store.TaskSessionCommand]
) -> list[store.Install]:
    installs: list[store.Install] = []
    seen: set[int] = set()
    for command in commands:
        if command.matched_install_id is None or command.matched_install_id in seen:
            continue
        inst = store.get_install(db, command.matched_install_id)
        if inst is not None:
            installs.append(inst)
            seen.add(inst.id)
    return installs


def _requires_confirmation(policy: str, base_url: str) -> bool:
    """Thin alias; the policy lives in why.llm so CLI and web share one rule."""
    from why.llm import requires_confirmation

    return requires_confirmation(policy, base_url)


@sessions_app.command("summarize")
def sessions_summarize(
    session_id: int,
    print_payload: bool = typer.Option(False, "--print-payload"),
) -> None:
    from why.config import load_llm_ignore_patterns
    from why.llm import (
        PROMPT_VERSION,
        SYSTEM_PROMPT_V1,
        build_task_payload,
        build_user_prompt,
        normalized_payload_hash,
        summarize_openai_compatible,
    )

    db = ensure_ready()
    session = store.get_task_session(db, session_id)
    if session is None:
        console.print(f"[red]No session with id {session_id}[/red]")
        raise typer.Exit(1)
    commands = store.list_task_session_commands(db, session.id)
    cfg = load_config()
    llm_cfg = cfg["llm"]
    payload = build_task_payload(
        session,
        commands,
        _known_installs_for_commands(db, commands),
        max_commands=int(llm_cfg["max_input_commands"]),
        llm_ignore_patterns=load_llm_ignore_patterns(),
    )
    if print_payload:
        console.print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if not llm_cfg["enabled"]:
        console.print("[yellow]LLM is disabled. Run `why llm configure` first.[/yellow]")
        raise typer.Exit(1)
    if _requires_confirmation(str(llm_cfg["confirm_before_send"]), str(llm_cfg["base_url"])):
        console.print(f"Endpoint: {llm_cfg['base_url']}")
        console.print(f"Model:    {llm_cfg['model']}")
        if not typer.confirm("Send this transcript to the configured LLM?", default=False):
            raise typer.Exit(0)
    user_prompt = build_user_prompt(payload)
    try:
        summary = summarize_openai_compatible(
            base_url=str(llm_cfg["base_url"]),
            api_key=os.environ.get(str(llm_cfg["api_key_env"])),
            model=str(llm_cfg["model"]),
            system_prompt=SYSTEM_PROMPT_V1,
            user_prompt=user_prompt,
            timeout_seconds=int(llm_cfg["timeout_seconds"]),
        )
    except RuntimeError as e:
        store.set_task_session_summary_status(db, session.id, "failed")
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e
    if llm_cfg["store_summaries"]:
        store.save_task_session_summary(
            db,
            session.id,
            provider=str(llm_cfg["provider"]),
            model=str(llm_cfg["model"]),
            endpoint=str(llm_cfg["base_url"]),
            prompt_version=PROMPT_VERSION,
            input_hash=normalized_payload_hash(payload),
            summary_markdown=summary,
        )
    else:
        # save_task_session_summary is what normally sets 'complete'. Without this the
        # session would stay 'none' and reappear in "needs summary" views forever.
        store.set_task_session_summary_status(db, session.id, "complete")
        console.print("[dim]store_summaries = false — not saved to the database.[/dim]")
    console.print(summary)


@sessions_app.command("ignore-llm")
def sessions_ignore_llm(session_id: int) -> None:
    db = ensure_ready()
    store.set_task_session_summary_status(db, session_id, "ignored")
    console.print(f"Session #{session_id} marked as not needing an LLM summary.")


@sessions_app.command("delete")
def sessions_delete(
    session_id: int,
    purge: bool = typer.Option(
        False,
        "--purge",
        help="Irreversibly remove the transcript and its commands and summaries, "
        "instead of hiding it.",
    ),
) -> None:
    """Delete a saved session.

    By default this is a soft delete: the session disappears from the CLI and web UI
    but the row remains, matching `why delete` for installs. Use --purge to remove
    the transcript from the database entirely.
    """
    db = ensure_ready()
    if store.get_task_session(db, session_id) is None:
        console.print(f"[red]No session with id {session_id}[/red]")
        raise typer.Exit(1)
    if purge:
        store.purge_task_session(db, session_id)
        console.print(f"Purged session #{session_id} and its transcript.")
    else:
        store.soft_delete_task_session(db, session_id)
        console.print(f"Deleted session #{session_id}. Use --purge to erase the transcript.")


@sessions_app.command("unignore-llm")
def sessions_unignore_llm(session_id: int) -> None:
    """Make a session eligible for an LLM summary again (undoes `ignore-llm`)."""
    db = ensure_ready()
    store.set_task_session_summary_status(db, session_id, "none")
    console.print(f"Session #{session_id} is eligible for an LLM summary again.")


llm_app = typer.Typer(help="Configure LLM task summaries.")
app.add_typer(llm_app, name="llm")


@llm_app.command("configure")
def llm_configure() -> None:
    cfg = load_config()
    llm_cfg = cfg["llm"]
    try:
        llm_cfg["enabled"] = typer.confirm(
            "Enable LLM summaries?", default=bool(llm_cfg["enabled"])
        )
        llm_cfg["provider"] = typer.prompt("Provider", default=str(llm_cfg["provider"]))
        llm_cfg["base_url"] = typer.prompt("Base URL", default=str(llm_cfg["base_url"]))
        llm_cfg["model"] = typer.prompt("Model", default=str(llm_cfg["model"]))
        llm_cfg["api_key_env"] = typer.prompt(
            "API key env var", default=str(llm_cfg["api_key_env"])
        )
        llm_cfg["confirm_before_send"] = typer.prompt(
            "Confirm before send (always/remote/never)",
            default=str(llm_cfg["confirm_before_send"]),
        )
    except (click.Abort, EOFError):
        # CLAUDE.md: never assume a TTY. Scripts, Dockerfiles and CI must be able
        # to call this without hanging or aborting.
        console.print(
            "\n[yellow]No input available — LLM settings unchanged.[/yellow]\n"
            r"Edit the \[llm] section of ~/.why/config.toml, or use the web UI "
            "at /settings/llm."
        )
        return
    write_config(cfg)
    console.print("LLM settings saved.")


@llm_app.command("test")
def llm_test() -> None:
    cfg = load_config()["llm"]
    if not cfg["enabled"]:
        console.print("[yellow]LLM is disabled.[/yellow]")
        raise typer.Exit(1)
    from why.llm import summarize_openai_compatible

    console.print(f"Provider: {cfg['provider']}")
    console.print(f"Endpoint: {cfg['base_url']}")
    console.print(f"Model: {cfg['model']}")
    # Actually contact the endpoint. Printing config and exiting 0 meant a wrong key
    # or an unreachable host still "passed", and only failed later at summarize time.
    #
    # Deliberately NOT gated on confirm_before_send: that policy protects terminal
    # transcripts, and this sends only the fixed two-line probe below - no session
    # data. The user ran `llm test` precisely to contact the endpoint, so prompting
    # for confirmation would be asking them to confirm the thing they just asked for.
    try:
        summarize_openai_compatible(
            base_url=str(cfg["base_url"]),
            api_key=os.environ.get(str(cfg["api_key_env"])),
            model=str(cfg["model"]),
            system_prompt="You are a connectivity check.",
            user_prompt="Reply with the single word: ok",
            timeout_seconds=int(cfg["timeout_seconds"]),
        )
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e
    console.print("[green]✓[/green] endpoint reachable and responded.")


# ---------------------------------------------------------------------------
# why purposes — manage purpose categories
# ---------------------------------------------------------------------------

purposes_app = typer.Typer(help="Manage purpose categories.")
app.add_typer(purposes_app, name="purposes")


@purposes_app.command("list")
def purposes_list() -> None:
    """List all purpose categories."""
    db = ensure_ready()
    rows = store.list_purposes(db)
    if not rows:
        console.print("No purposes defined.")
        return
    t = Table()
    for col in ("key", "label", "color", "order", "built-in"):
        t.add_column(col)
    for p in rows:
        t.add_row(p.key, p.label, p.color, str(p.sort_order), "yes" if p.built_in else "no")
    console.print(t)


@purposes_app.command("add")
def purposes_add(
    key: str = typer.Argument(..., help="Unique key (e.g. 'work')"),
    label: str = typer.Option(..., "--label", "-l", help="Display label"),
    color: str = typer.Option("#6b7280", "--color", "-c", help="Hex color"),
    order: int = typer.Option(99, "--order", "-o", help="Sort order"),
) -> None:
    """Add a new purpose category."""
    db = ensure_ready()
    try:
        p = store.create_purpose(db, key=key, label=label, color=color, sort_order=order)
        console.print(f"Added purpose '{p.key}': {p.label}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@purposes_app.command("edit")
def purposes_edit(
    key: str = typer.Argument(..., help="Key of the purpose to edit"),
    label: str | None = typer.Option(None, "--label", "-l"),
    color: str | None = typer.Option(None, "--color", "-c"),
    order: int | None = typer.Option(None, "--order", "-o"),
) -> None:
    """Edit an existing purpose category (built-in or custom)."""
    db = ensure_ready()
    try:
        p = store.update_purpose(db, key, label=label, color=color, sort_order=order)
        console.print(f"Updated purpose '{p.key}': {p.label}")
    except (KeyError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@purposes_app.command("delete")
def purposes_delete(
    key: str = typer.Argument(..., help="Key of the purpose to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Delete a custom purpose category (built-in purposes cannot be deleted)."""
    db = ensure_ready()
    try:
        if not yes:
            typer.confirm(f"Delete purpose '{key}'?", abort=True)
        store.delete_purpose(db, key)
        console.print(f"Deleted purpose '{key}'.")
    except (KeyError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
