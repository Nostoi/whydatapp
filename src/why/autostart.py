from __future__ import annotations

import subprocess
from pathlib import Path

LABEL = "io.why.serve"


def _macos_plist(why_path: str, port: int) -> str:
    home = Path.home()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{why_path}</string>
    <string>serve</string>
    <string>--no-open</string>
    <string>--port</string><string>{port}</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>{home}/.why/web.log</string>
  <key>StandardErrorPath</key><string>{home}/.why/web.log</string>
</dict></plist>
"""


def install_macos_launchd(*, why_path: str, port: int, dry_run: bool = False) -> str:
    plist = _macos_plist(why_path, port)
    if dry_run:
        return plist
    target = Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(plist)
    subprocess.run(["launchctl", "unload", str(target)], capture_output=True)
    subprocess.run(["launchctl", "load", str(target)], check=False)
    return plist


def uninstall_macos_launchd() -> None:
    target = Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
    if target.exists():
        subprocess.run(["launchctl", "unload", str(target)], capture_output=True)
        target.unlink()


def _linux_unit(why_path: str, port: int) -> str:
    return f"""[Unit]
Description=why? local web UI

[Service]
ExecStart={why_path} serve --no-open --port {port}
Restart=on-failure

[Install]
WantedBy=default.target
"""


def install_linux_systemd(*, why_path: str, port: int, dry_run: bool = False) -> str:
    unit = _linux_unit(why_path, port)
    if dry_run:
        return unit
    target = Path.home() / ".config/systemd/user/why.service"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(unit)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "--user", "enable", "--now", "why.service"], check=False)
    return unit


def uninstall_linux_systemd() -> None:
    target = Path.home() / ".config/systemd/user/why.service"
    if target.exists():
        subprocess.run(["systemctl", "--user", "disable", "--now", "why.service"], check=False)
        target.unlink()
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
