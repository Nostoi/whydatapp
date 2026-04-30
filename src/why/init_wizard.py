from __future__ import annotations

import socket

import typer
from rich.console import Console

from why.bootstrap import ensure_ready
from why.config import load_config, write_config
from why.paths import why_home
from why.shells.installer import (
    copy_hook_to_home,
    detect_shell,
    install_into_rc,
    rc_file_for,
)

_TIER1 = ("brew", "npm", "pnpm", "yarn", "bun", "pip", "pipx", "uv", "cargo", "git")
_TIER2 = ("gem", "go", "apt", "mas", "vscode", "docker")


def run_wizard(console: Console) -> int:
    home = why_home()
    console.print(f"[bold]why?[/bold] setup — installing to {home}")

    ensure_ready()
    cfg = load_config()

    default_label = socket.gethostname()
    label = typer.prompt("Device label", default=default_label)
    cfg["device"]["label"] = label

    console.print("\n[bold]Tracked managers (Tier-1)[/bold]")
    for m in _TIER1:
        cfg["managers"][m] = typer.confirm(f"  Track {m}?", default=True)

    if typer.confirm(
        "\nEnable Tier-2 managers (gem, go, apt, mas, vscode, docker)?", default=False
    ):
        for m in _TIER2:
            cfg["managers"][m] = typer.confirm(f"  Track {m}?", default=False)

    port_str = typer.prompt("Web UI port", default=str(cfg["web"]["port"]))
    try:
        cfg["web"]["port"] = int(port_str)
    except ValueError:
        cfg["web"]["port"] = 7873

    cfg["web"]["autostart"] = typer.confirm("Autostart web UI on login?", default=False)

    shell = detect_shell()
    rc = rc_file_for(shell)
    console.print(f"\nDetected shell: [bold]{shell}[/bold] → rc file: {rc}")
    if typer.confirm("Install hook block into rc file?", default=True):
        hook_path = copy_hook_to_home(shell, home)
        install_into_rc(rc, hook_path=hook_path, shell=shell)
        console.print(f"  [green]✓[/green] hook installed; restart your shell or `source {rc}`")
    else:
        console.print("  [yellow]skipped — you can rerun `why init` later[/yellow]")

    write_config(cfg)

    if cfg["web"]["autostart"]:
        try:
            import sys

            from why.autostart import install_linux_systemd, install_macos_launchd
            why_bin = "why"
            if sys.platform == "darwin":
                install_macos_launchd(why_path=why_bin, port=cfg["web"]["port"])
            elif sys.platform.startswith("linux"):
                install_linux_systemd(why_path=why_bin, port=cfg["web"]["port"])
            console.print("  [green]✓[/green] autostart installed")
        except Exception as e:
            console.print(f"  [yellow]autostart failed: {e}[/yellow]")

    console.print(
        "\n[bold green]Done.[/bold green] Try: [bold]brew install ripgrep[/bold]"
        " (or any tracked manager)."
    )
    return 0
