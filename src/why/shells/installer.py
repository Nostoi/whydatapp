from __future__ import annotations

import os
import re
from importlib import resources
from pathlib import Path

BLOCK_BEGIN = "# >>> why-cli hook >>>"
BLOCK_END = "# <<< why-cli hook <<<"

SHELLS = ("zsh", "bash", "fish")

_BLOCK_RE = re.compile(
    rf"\n?{re.escape(BLOCK_BEGIN)}.*?{re.escape(BLOCK_END)}\n?",
    re.DOTALL,
)

# `WHY_HOOK_VERSION=3` in zsh/bash, `set -g WHY_HOOK_VERSION 3` in fish.
_VERSION_RE = re.compile(r"^\s*(?:set -g\s+)?WHY_HOOK_VERSION[= ]\s*(\d+)\s*$", re.MULTILINE)


def detect_shell() -> str:
    s = os.environ.get("SHELL", "")
    name = s.rsplit("/", 1)[-1]
    if name in ("zsh", "bash", "fish"):
        return name
    return "zsh"


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


def packaged_hook_text(shell: str) -> str:
    if shell not in SHELLS:
        raise ValueError(f"unsupported shell: {shell}")
    text = resources.files("why.shells").joinpath(f"hook.{shell}").read_text()
    return text


def copy_hook_to_home(shell: str, why_home: Path) -> Path:
    src = packaged_hook_text(shell)
    dest = hook_target_for(shell, why_home)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(src)
    return dest


def _parse_hook_version(text: str) -> int | None:
    m = _VERSION_RE.search(text)
    return int(m.group(1)) if m else None


def packaged_hook_version(shell: str) -> int:
    """The version the *shipped* hook declares.

    Raises if the marker is missing: a hook that loses it would silently opt out
    of auto-refresh for every user, forever. tests/unit/test_hook_refresh.py
    guards this at build time.
    """
    version = _parse_hook_version(packaged_hook_text(shell))
    if version is None:
        raise ValueError(f"packaged hook.{shell} declares no WHY_HOOK_VERSION")
    return version


def installed_hook_version(shell: str, why_home: Path) -> int | None:
    """Version of the hook in `why_home`, or None if absent/unversioned.

    Callers must distinguish "no file" from "unversioned file" themselves via
    `hook_target_for(...).exists()` — resurrecting a hook the user removed with
    `why uninstall` would make uninstall non-convergent.
    """
    target = hook_target_for(shell, why_home)
    try:
        text = target.read_text()
    except OSError:
        return None
    return _parse_hook_version(text)


def refresh_stale_hooks(why_home: Path) -> list[tuple[str, int | None, int]]:
    """Rewrite every *already installed* hook file that predates this release.

    Returns (shell, old_version, new_version) per refreshed file; empty when
    everything is current. Never raises: a read-only ~/.why also means
    hook.log is unwritable, so there is nowhere to report the failure.

    Only the sourced payload changes — the rc-file block that sources it is
    untouched, which is what makes doing this unprompted safe.
    """
    refreshed: list[tuple[str, int | None, int]] = []
    for shell in SHELLS:
        target = hook_target_for(shell, why_home)
        if not target.exists():
            continue
        packaged = packaged_hook_version(shell)
        installed = installed_hook_version(shell, why_home)
        if installed is not None and installed >= packaged:
            continue
        try:
            copy_hook_to_home(shell, why_home)
        except OSError:
            continue
        refreshed.append((shell, installed, packaged))
    return refreshed


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
    if name.endswith(".zsh"):
        return "zsh"
    if name.endswith(".bash"):
        return "bash"
    if name.endswith(".fish"):
        return "fish"
    return "zsh"
