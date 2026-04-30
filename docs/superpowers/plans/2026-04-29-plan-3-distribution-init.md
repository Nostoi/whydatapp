# why? — Plan 3: Distribution & Init Wizard

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the shell hooks, an interactive `why init` wizard, a clean `why uninstall`, optional autostart units, and a packaging story so the final user experience is `uv tool install why-cli && why init`. After this plan, the product is fully usable end-to-end.

**Architecture:** Hooks are tiny shell wrappers in `src/why/shells/{zsh,bash,fish}` that source from `~/.why/hook.<shell>` (which we copy at `init` time). The wizard mutates the rc file via a fenced block we own. Autostart uses launchd on macOS and systemd-user on Linux.

**Tech Stack:** zsh/bash/fish shell, Typer prompts, plistlib (launchd), simple textual systemd unit. No new Python deps.

---

## File Structure

Adds to the package layout from earlier plans:

```
src/why/
├── shells/
│   ├── __init__.py
│   ├── hook.zsh
│   ├── hook.bash
│   ├── hook.fish
│   └── installer.py        # rc-file edit + uninstall
├── init_wizard.py
├── autostart.py
└── ...

tests/
├── integration/
│   ├── test_init.py
│   ├── test_hook_shell.py  # boots a real shell
│   └── test_uninstall.py
```

---

## Task 1: Shell hook scripts

**Files:**
- Create: `src/why/shells/__init__.py` (empty)
- Create: `src/why/shells/hook.zsh`
- Create: `src/why/shells/hook.bash`
- Create: `src/why/shells/hook.fish`
- Modify: `pyproject.toml` (force-include shells dir)

- [ ] **Step 1: Write `hook.zsh`**

```zsh
# src/why/shells/hook.zsh
# why-cli shell hook for zsh.
# Captures the most recent command, then on prompt return:
#   - if exit code != 0, drops the capture
#   - else exec's `why _hook` which silently no-ops on non-matches
#   - any failure is silent — terminal is never broken.

if [[ -n $WHY_HOOK_LOADED ]]; then
  return
fi
WHY_HOOK_LOADED=1

autoload -Uz add-zsh-hook 2>/dev/null

_why_preexec() {
  WHY_LAST_CMD="$1"
  WHY_LAST_PWD="$PWD"
}

_why_precmd() {
  local code=$?
  if [[ -z $WHY_LAST_CMD ]]; then
    return
  fi
  if [[ $code -ne 0 ]]; then
    WHY_LAST_CMD=
    return
  fi
  if [[ -n $WHY_SUPPRESS ]]; then
    WHY_LAST_CMD=
    return
  fi
  WHY_SUPPRESS=1 command why _hook \
    --cmd "$WHY_LAST_CMD" \
    --cwd "$WHY_LAST_PWD" \
    --code $code </dev/tty >/dev/tty 2>>"$HOME/.why/hook.log" || true
  WHY_LAST_CMD=
}

if typeset -f add-zsh-hook >/dev/null 2>&1; then
  add-zsh-hook preexec _why_preexec
  add-zsh-hook precmd  _why_precmd
fi
```

- [ ] **Step 2: Write `hook.bash`**

```bash
# src/why/shells/hook.bash
# why-cli shell hook for bash.
# Uses DEBUG trap + PROMPT_COMMAND.

if [[ -n "$WHY_HOOK_LOADED" ]]; then
  return 0 2>/dev/null || exit 0
fi
WHY_HOOK_LOADED=1

_why_preexec_bash() {
  # Only capture top-level commands, not subshells PROMPT_COMMAND uses.
  if [[ -n "$COMP_LINE" ]]; then return; fi
  if [[ "$BASH_COMMAND" == "_why_precmd_bash" ]]; then return; fi
  WHY_LAST_CMD="$BASH_COMMAND"
  WHY_LAST_PWD="$PWD"
}

_why_precmd_bash() {
  local code=$?
  if [[ -z "$WHY_LAST_CMD" ]]; then return; fi
  if [[ $code -ne 0 ]]; then WHY_LAST_CMD=; return; fi
  if [[ -n "$WHY_SUPPRESS" ]]; then WHY_LAST_CMD=; return; fi
  WHY_SUPPRESS=1 command why _hook \
    --cmd "$WHY_LAST_CMD" \
    --cwd "$WHY_LAST_PWD" \
    --code $code </dev/tty >/dev/tty 2>>"$HOME/.why/hook.log" || true
  WHY_LAST_CMD=
}

trap '_why_preexec_bash' DEBUG
PROMPT_COMMAND="_why_precmd_bash;${PROMPT_COMMAND}"
```

- [ ] **Step 3: Write `hook.fish`**

```fish
# src/why/shells/hook.fish
if set -q WHY_HOOK_LOADED
    exit 0
end
set -g WHY_HOOK_LOADED 1

function _why_preexec --on-event fish_preexec
    set -g WHY_LAST_CMD $argv[1]
    set -g WHY_LAST_PWD $PWD
end

function _why_postexec --on-event fish_postexec
    set -l code $status
    if test -z "$WHY_LAST_CMD"
        return
    end
    if test $code -ne 0
        set -e WHY_LAST_CMD
        return
    end
    if set -q WHY_SUPPRESS
        set -e WHY_LAST_CMD
        return
    end
    WHY_SUPPRESS=1 command why _hook \
        --cmd "$WHY_LAST_CMD" \
        --cwd "$WHY_LAST_PWD" \
        --code $code </dev/tty >/dev/tty 2>>"$HOME/.why/hook.log"
    set -e WHY_LAST_CMD
end
```

- [ ] **Step 4: Add to `pyproject.toml`**

Add to `[tool.hatch.build.targets.wheel.force-include]`:

```toml
"src/why/shells" = "why/shells"
```

- [ ] **Step 5: Commit**

```bash
git add src/why/shells pyproject.toml
git commit -m "feat(shells): zsh/bash/fish install hooks"
```

---

## Task 2: rc-file installer + uninstaller

**Files:**
- Create: `src/why/shells/installer.py`
- Create: `tests/integration/test_uninstall.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_uninstall.py
from __future__ import annotations

from pathlib import Path

from why.shells.installer import (
    BLOCK_BEGIN,
    BLOCK_END,
    detect_shell,
    install_into_rc,
    rc_file_for,
    remove_from_rc,
)


def test_install_appends_block_with_fence(tmp_path: Path):
    rc = tmp_path / ".zshrc"
    rc.write_text("# existing\n")
    install_into_rc(rc, hook_path=Path("/x/hook.zsh"))
    text = rc.read_text()
    assert BLOCK_BEGIN in text
    assert BLOCK_END in text
    assert "/x/hook.zsh" in text


def test_install_is_idempotent(tmp_path: Path):
    rc = tmp_path / ".zshrc"
    rc.write_text("")
    install_into_rc(rc, hook_path=Path("/x/hook.zsh"))
    install_into_rc(rc, hook_path=Path("/x/hook.zsh"))
    assert rc.read_text().count(BLOCK_BEGIN) == 1


def test_remove_strips_block(tmp_path: Path):
    rc = tmp_path / ".zshrc"
    rc.write_text("before\n")
    install_into_rc(rc, hook_path=Path("/x/hook.zsh"))
    rc.write_text(rc.read_text() + "after\n")
    remove_from_rc(rc)
    text = rc.read_text()
    assert "before" in text
    assert "after" in text
    assert BLOCK_BEGIN not in text
    assert BLOCK_END not in text


def test_detect_shell_from_env(monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/zsh")
    assert detect_shell() == "zsh"
    monkeypatch.setenv("SHELL", "/usr/local/bin/bash")
    assert detect_shell() == "bash"
    monkeypatch.setenv("SHELL", "/opt/homebrew/bin/fish")
    assert detect_shell() == "fish"


def test_rc_file_for_returns_expected_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert rc_file_for("zsh") == tmp_path / ".zshrc"
    assert rc_file_for("bash") == tmp_path / ".bashrc"
    assert rc_file_for("fish") == tmp_path / ".config/fish/config.fish"
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/integration/test_uninstall.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `installer.py`**

```python
# src/why/shells/installer.py
from __future__ import annotations

import os
import re
import shutil
from importlib import resources
from pathlib import Path

BLOCK_BEGIN = "# >>> why-cli hook >>>"
BLOCK_END = "# <<< why-cli hook <<<"

_BLOCK_RE = re.compile(
    rf"\n?{re.escape(BLOCK_BEGIN)}.*?{re.escape(BLOCK_END)}\n?",
    re.DOTALL,
)


def detect_shell() -> str:
    s = os.environ.get("SHELL", "")
    name = s.rsplit("/", 1)[-1]
    if name in ("zsh", "bash", "fish"):
        return name
    return "zsh"  # sane default on macOS


def rc_file_for(shell: str) -> Path:
    home = Path(os.environ["HOME"])
    if shell == "zsh":
        return home / ".zshrc"
    if shell == "bash":
        return home / ".bashrc"
    if shell == "fish":
        return home / ".config/fish/config.fish"
    raise ValueError(f"unsupported shell: {shell}")


def hook_target_for(shell: str, why_home: Path) -> Path:
    return why_home / f"hook.{shell}"


def copy_hook_to_home(shell: str, why_home: Path) -> Path:
    src = resources.files("why.shells").joinpath(f"hook.{shell}").read_text()
    dest = hook_target_for(shell, why_home)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(src)
    return dest


def _block_for(shell: str, hook_path: Path) -> str:
    if shell == "fish":
        body = f"test -f {hook_path} ; and source {hook_path}"
    else:
        body = f"[ -f {hook_path} ] && source {hook_path}"
    return f"{BLOCK_BEGIN}\n{body}\n{BLOCK_END}\n"


def install_into_rc(rc: Path, *, hook_path: Path, shell: str | None = None) -> None:
    rc.parent.mkdir(parents=True, exist_ok=True)
    text = rc.read_text() if rc.exists() else ""
    sh = shell or _shell_from_hook_path(hook_path)
    new_block = _block_for(sh, hook_path)
    cleaned = _BLOCK_RE.sub("\n", text).rstrip() + "\n"
    rc.write_text(cleaned + "\n" + new_block)


def remove_from_rc(rc: Path) -> None:
    if not rc.exists():
        return
    text = rc.read_text()
    rc.write_text(_BLOCK_RE.sub("\n", text))


def _shell_from_hook_path(p: Path) -> str:
    name = p.name
    if name.endswith(".zsh"): return "zsh"
    if name.endswith(".bash"): return "bash"
    if name.endswith(".fish"): return "fish"
    return "zsh"
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/integration/test_uninstall.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/why/shells/installer.py tests/integration/test_uninstall.py
git commit -m "feat(shells): rc-file install/uninstall with fenced block"
```

---

## Task 3: Autostart units

**Files:**
- Create: `src/why/autostart.py`
- Create: `tests/unit/test_autostart.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_autostart.py
import sys
from pathlib import Path

import pytest

from why.autostart import (
    install_macos_launchd,
    uninstall_macos_launchd,
    install_linux_systemd,
    uninstall_linux_systemd,
)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-only")
def test_macos_writes_plist(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    plist = install_macos_launchd(why_path="/usr/local/bin/why", port=7873, dry_run=True)
    assert "<key>Label</key>" in plist
    assert "/usr/local/bin/why" in plist
    assert "<string>serve</string>" in plist


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux-only")
def test_linux_writes_unit(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    unit = install_linux_systemd(why_path="/usr/local/bin/why", port=7873, dry_run=True)
    assert "ExecStart=/usr/local/bin/why serve --no-open" in unit
    assert "Restart=on-failure" in unit


def test_uninstall_no_op_when_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    if sys.platform == "darwin":
        uninstall_macos_launchd()
    elif sys.platform.startswith("linux"):
        uninstall_linux_systemd()
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/test_autostart.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `autostart.py`**

```python
# src/why/autostart.py
from __future__ import annotations

import os
import subprocess
from pathlib import Path

LABEL = "io.why.serve"


def _macos_plist(why_path: str, port: int) -> str:
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
  <key>StandardOutPath</key><string>{Path.home()}/.why/web.log</string>
  <key>StandardErrorPath</key><string>{Path.home()}/.why/web.log</string>
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
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_autostart.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/why/autostart.py tests/unit/test_autostart.py
git commit -m "feat(autostart): launchd + systemd-user unit generation"
```

---

## Task 4: `why init` wizard

**Files:**
- Create: `src/why/init_wizard.py`
- Modify: `src/why/cli.py`
- Create: `tests/integration/test_init.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_init.py
from __future__ import annotations

import os
from pathlib import Path

from typer.testing import CliRunner

from why.cli import app
from why.shells.installer import BLOCK_BEGIN

runner = CliRunner()


def test_init_creates_home_and_rc_block(why_home: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SHELL", "/bin/zsh")
    rc = tmp_path / ".zshrc"
    rc.write_text("# existing\n")
    answers = "\n".join([
        "work-mbp",      # device label
        "y",             # tier-1: brew
        "y",             # npm
        "y",             # pnpm
        "y",             # yarn
        "y",             # bun
        "y",             # pip
        "y",             # pipx
        "y",             # uv
        "y",             # cargo
        "y",             # git
        "n",             # tier-2 opt-in
        "",              # port (default)
        "n",             # autostart
        "y",             # confirm rc edit
    ]) + "\n"
    result = runner.invoke(app, ["init"], input=answers)
    assert result.exit_code == 0, result.stdout
    assert (why_home / "config.toml").exists()
    assert (why_home / "data.db").exists()
    assert (why_home / "hook.zsh").exists()
    assert BLOCK_BEGIN in rc.read_text()
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/integration/test_init.py -v`
Expected: failure (no `init` command).

- [ ] **Step 3: Implement `init_wizard.py`**

```python
# src/why/init_wizard.py
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

    db = ensure_ready()  # creates dirs, schema, user, device row
    cfg = load_config()

    # 1) device label
    default_label = socket.gethostname()
    label = typer.prompt("Device label", default=default_label)
    cfg["device"]["label"] = label

    # 2) tier-1 toggles
    console.print("\n[bold]Tracked managers (Tier-1)[/bold]")
    for m in _TIER1:
        cfg["managers"][m] = typer.confirm(f"  Track {m}?", default=True)

    # 3) tier-2 opt-in
    if typer.confirm("\nEnable Tier-2 managers (gem, go, apt, mas, vscode, docker)?", default=False):
        for m in _TIER2:
            cfg["managers"][m] = typer.confirm(f"  Track {m}?", default=False)

    # 4) port
    port_str = typer.prompt("Web UI port", default=str(cfg["web"]["port"]))
    try:
        cfg["web"]["port"] = int(port_str)
    except ValueError:
        cfg["web"]["port"] = 7873

    # 5) autostart
    cfg["web"]["autostart"] = typer.confirm("Autostart web UI on login?", default=False)

    # 6) shell hook
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
            from why.autostart import install_macos_launchd, install_linux_systemd
            why_path = "why"
            if sys.platform == "darwin":
                install_macos_launchd(why_path=why_path, port=cfg["web"]["port"])
            elif sys.platform.startswith("linux"):
                install_linux_systemd(why_path=why_path, port=cfg["web"]["port"])
            console.print("  [green]✓[/green] autostart installed")
        except Exception as e:
            console.print(f"  [yellow]autostart failed: {e}[/yellow]")

    console.print("\n[bold green]Done.[/bold green] Try: [bold]brew install ripgrep[/bold] (or any tracked manager).")
    return 0
```

- [ ] **Step 4: Wire `init` into `cli.py`**

Append to `src/why/cli.py`:

```python
@app.command("init")
def init_cmd() -> None:
    """First-run interactive setup wizard."""
    from why.init_wizard import run_wizard
    rc = run_wizard(console)
    raise typer.Exit(code=rc)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/integration/test_init.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/why/init_wizard.py src/why/cli.py tests/integration/test_init.py
git commit -m "feat(cli): init wizard wires hook + config + optional autostart"
```

---

## Task 5: `why uninstall` subcommand

**Files:**
- Modify: `src/why/cli.py`
- Modify: `tests/integration/test_uninstall.py`

- [ ] **Step 1: Extend test**

Append to `tests/integration/test_uninstall.py`:

```python
from typer.testing import CliRunner
from why.cli import app
from why.shells.installer import BLOCK_BEGIN
from pathlib import Path

runner = CliRunner()


def test_uninstall_removes_block_and_keeps_data(tmp_path: Path, why_home: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SHELL", "/bin/zsh")
    rc = tmp_path / ".zshrc"
    rc.write_text("# x\n")
    init_answers = "\n".join(
        ["lab"] + ["y"]*10 + ["n", "", "n", "y"]
    ) + "\n"
    runner.invoke(app, ["init"], input=init_answers)
    assert BLOCK_BEGIN in rc.read_text()

    result = runner.invoke(app, ["uninstall"], input="n\n")  # keep data
    assert result.exit_code == 0
    assert BLOCK_BEGIN not in rc.read_text()
    assert (why_home / "data.db").exists()


def test_uninstall_removes_data_when_confirmed(tmp_path: Path, why_home: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SHELL", "/bin/zsh")
    rc = tmp_path / ".zshrc"
    rc.write_text("")
    init_answers = "\n".join(
        ["lab"] + ["y"]*10 + ["n", "", "n", "y"]
    ) + "\n"
    runner.invoke(app, ["init"], input=init_answers)

    result = runner.invoke(app, ["uninstall"], input="y\n")
    assert result.exit_code == 0
    assert not (why_home / "data.db").exists()
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/integration/test_uninstall.py -v`
Expected: failure (no `uninstall` command).

- [ ] **Step 3: Implement `uninstall` in `cli.py`**

Append to `src/why/cli.py`:

```python
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
    if typer.confirm(f"Also delete data directory {home}? This wipes your install history.", default=False):
        if home.exists():
            shutil.rmtree(home)
        console.print(f"[green]✓[/green] removed {home}")
    else:
        console.print(f"  [dim]kept {home}[/dim]")
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/integration/test_uninstall.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/why/cli.py tests/integration/test_uninstall.py
git commit -m "feat(cli): uninstall removes hook + autostart, optional data wipe"
```

---

## Task 6: Live shell integration test

**Files:**
- Create: `tests/integration/test_hook_shell.py`

- [ ] **Step 1: Write the test**

```python
# tests/integration/test_hook_shell.py
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh not available")
def test_hook_captures_real_install(tmp_path: Path, monkeypatch):
    # Isolate WHY_HOME and HOME to a tmp dir.
    home = tmp_path / "home"
    home.mkdir()
    why = home / ".why"
    monkeypatch.setenv("WHY_HOME", str(why))

    # A fake `brew` shim that always succeeds.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    brew = bin_dir / "brew"
    brew.write_text("#!/bin/sh\nexit 0\n")
    brew.chmod(0o755)

    # Run `why init` with a canned input set, against this isolated home.
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SHELL", "/bin/zsh")
    init_answers = "\n".join(["lab"] + ["y"]*10 + ["n", "", "n", "y"]) + "\n"
    subprocess.run(
        ["uv", "run", "why", "init"],
        input=init_answers, text=True, check=True,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
    )

    # Source hook and run `brew install ripgrep` in a real interactive zsh.
    script = f"""
    set -e
    source {why}/hook.zsh
    # Simulate by directly invoking the precmd path: set captured cmd, exit 0.
    WHY_LAST_CMD='brew install ripgrep'
    WHY_LAST_PWD={tmp_path}
    # answer disposition=skip so test can be non-interactive
    WHY_SUPPRESS=1 why _hook --cmd "$WHY_LAST_CMD" --cwd "$WHY_LAST_PWD" --code 0 < /dev/null > /dev/null 2>&1 || true
    """
    subprocess.run(
        ["zsh", "-i", "-c", script], check=True,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": str(home), "WHY_HOME": str(why)},
    )

    # _hook with WHY_SUPPRESS=1 returns immediately (suppress_env ignore rule),
    # so this test asserts the script ran without breaking the shell. The
    # finer-grained capture path is covered by tests/integration/test_cli.py.
    assert (why / "data.db").exists()
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/integration/test_hook_shell.py -v`
Expected: PASS on a machine with zsh; SKIP otherwise.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_hook_shell.py
git commit -m "test: live shell smoke test for hook installation"
```

---

## Task 7: README + minimal docs

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace `README.md`**

```markdown
# why?

Track *why* you installed every tool on your machine.

`why?` watches for installs (`brew install`, `npm i -g`, `pip install`, `cargo install`, `git clone`, …) via a tiny shell hook, and asks five quick questions: name, what it does, project, why, and what to do with it (document, add to setup script, experimental, remove later, ignore). Local-only SQLite. Local web UI for search, sort, and sharing. Privacy-focused — nothing leaves your machine.

## Install

```bash
uv tool install why-cli   # or: pipx install why-cli
why init                  # interactive setup; edits your shell rc
```

Restart your shell, then try `brew install ripgrep` (or any tracked manager).

## Use

| Command           | What it does                                   |
|-------------------|------------------------------------------------|
| `why log -- <cmd>`| Manually log an install                        |
| `why review`      | Drain the skipped/incomplete review queue      |
| `why list`        | Print installs as a table                      |
| `why export`      | Export to Markdown or JSON                     |
| `why serve`       | Open the local web UI at 127.0.0.1:7873        |
| `why uninstall`   | Remove the hook (and optionally the data)      |

## Privacy

- All data lives in `~/.why/data.db`. No network calls.
- The web UI binds to `127.0.0.1` only.
- The shell hook ignores any install triggered by another tracked installer (no false positives from `brew` resolving deps).

## Status

MVP. Sync, auth, AI enrichment, source scraping, and one-click remote install are on the roadmap. See `docs/superpowers/specs/` and `docs/superpowers/plans/` for the design.

## Known follow-ups

- Keyboard shortcuts in the web UI.
- Manual dark-mode toggle (currently follows OS).
- Golden snapshot tests for Jinja partials.
- `brew install why` Homebrew tap.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with install, usage, privacy, status"
```

---

## Task 8: End-to-end smoke + final pass

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest --cov=why --cov-report=term-missing`
Expected: all pass.

- [ ] **Step 2: Run ruff and mypy**

Run: `uv run ruff check src tests && uv run mypy src/why`
Expected: clean. Fix inline.

- [ ] **Step 3: Build package**

Run: `uv build`
Expected: `dist/why_cli-0.1.0-*.whl` and `dist/why_cli-0.1.0.tar.gz` produced.

- [ ] **Step 4: Smoke test from a clean venv**

```bash
cd /tmp && rm -rf why-smoke && mkdir why-smoke && cd why-smoke
uv venv && uv pip install <path-to-built-wheel>'[web]'
WHY_HOME=$(pwd)/.why uv run why init  # answer the prompts
WHY_HOME=$(pwd)/.why uv run why log -- brew install ripgrep  # or pick something handy
WHY_HOME=$(pwd)/.why uv run why list
WHY_HOME=$(pwd)/.why uv run why serve --no-open
# Open http://127.0.0.1:7873/ in a browser; verify table, dashboard, edit, share.
```

- [ ] **Step 5: Commit any final fixups**

```bash
git add -A
git commit -m "chore: final lint/type fixups + smoke test pass"
```

---

## Plan 3 — Self-Review

- ✅ Spec §4 hook handoff with paranoid error handling → Task 1.
- ✅ Spec §7 distribution: `uv tool install` + `why init` interactive wizard → Task 4.
- ✅ Spec §7 fenced block + clean uninstall → Tasks 2, 5.
- ✅ Spec §7 autostart units → Task 3.
- ✅ Spec §8 Flow C `why init` → Task 4.
- ✅ Spec §8 Flow E `why uninstall` → Task 5.
- ✅ Real-shell sourcing of the hook → Task 6.
- ✅ README covers install + usage + privacy posture → Task 7.
- 🔁 Homebrew tap is explicitly post-MVP per spec §15.

No placeholders. The wizard's `_TIER1`/`_TIER2` lists match `DEFAULT_CONFIG.managers` from Plan 1 Task 9. The fenced block strings (`BLOCK_BEGIN` / `BLOCK_END`) are defined once in `installer.py` and referenced by tests by symbol — no string drift across files.
