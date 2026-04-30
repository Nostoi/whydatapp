from __future__ import annotations

import os
import re
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
    if name.endswith(".zsh"):
        return "zsh"
    if name.endswith(".bash"):
        return "bash"
    if name.endswith(".fish"):
        return "fish"
    return "zsh"
