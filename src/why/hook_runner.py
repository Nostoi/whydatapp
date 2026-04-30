from __future__ import annotations

import os
import sys

from rich.console import Console

from why import store
from why.bootstrap import ensure_ready
from why.capture import capture
from why.config import load_user_ignore_patterns
from why.detect import IgnoreContext, match_install, should_ignore
from why.paths import log_path


def _parent_process_name() -> str | None:
    ppid = os.getppid()
    try:
        import subprocess
        r = subprocess.run(
            ["ps", "-o", "comm=", "-p", str(ppid)],
            capture_output=True, text=True, timeout=1.0,
        )
        if r.returncode != 0:
            return None
        name = r.stdout.strip().rsplit("/", 1)[-1]
        return name or None
    except Exception:
        return None


def _log_error(msg: str) -> None:
    try:
        with log_path("hook").open("a") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def run_hook(*, command: str, cwd: str, exit_code: int) -> int:
    """Returns 0 always. Triggers `why log` flow only when warranted."""
    try:
        if not command.strip():
            return 0
        match = match_install(command)
        if match is None:
            return 0

        db = ensure_ready()
        # WHY_SUPPRESS is set by the shell hook *for our environment* as a
        # shell-level recursion guard (see hook.zsh / hook.bash / hook.fish:
        # the shell itself checks $WHY_SUPPRESS before re-entering precmd).
        # We do NOT read it here — this Python process IS the hook, and
        # treating its own env flag as an "ignore me" signal silently
        # cancels every capture.
        ctx = IgnoreContext(
            command=command,
            cwd=cwd,
            exit_code=exit_code,
            interactive=sys.stdin.isatty() or os.environ.get("WHY_HOOK_FORCE_PROMPT") == "1",
            parent_process_name=_parent_process_name(),
            recent_duplicate=store.recent_duplicate_exists(
                db, command=command, install_dir=cwd, within_seconds=60
            ),
            user_ignore_patterns=load_user_ignore_patterns(),
        )
        if should_ignore(ctx):
            return 0

        capture(
            db,
            command_str=command,
            work_dir=cwd,
            enrich=True,
            console=Console(),
            input=sys.stdin,
            output=sys.stdout,
        )
        return 0
    except SystemExit:
        raise
    except Exception as e:
        _log_error(f"hook error: {e!r} cmd={command!r}")
        return 0
