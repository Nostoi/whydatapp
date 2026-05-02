from __future__ import annotations

import os
import sys
from datetime import UTC, datetime

from rich.console import Console

from why import store
from why.bootstrap import ensure_ready
from why.capture import capture, capture_removal
from why.config import load_user_ignore_patterns
from why.detect import IgnoreContext, match_install, match_uninstall, should_ignore
from why.paths import log_path
from why.redact import redact


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


def _parse_history(raw: str) -> list[str]:
    """Parse \x1e-delimited history string into a list of redacted commands.

    The shell hooks join decoded commands with ASCII record separator \\x1e.
    Empty entries and the install command itself are dropped.
    """
    if not raw:
        return []
    entries = [e.strip() for e in raw.split("\x1e")]
    return [redact(e) for e in entries if e]


def run_hook(*, command: str, cwd: str, exit_code: int, raw_history: str = "") -> int:
    """Returns 0 always. Triggers capture flow only when warranted."""
    try:
        if not command.strip():
            return 0

        db = ensure_ready()
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

        is_install = match_install(command) is not None
        is_uninstall = not is_install and match_uninstall(command) is not None

        if not is_install and not is_uninstall:
            return 0

        if is_install:
            install = capture(
                db,
                command_str=command,
                work_dir=cwd,
                enrich=True,
                console=Console(),
                input=sys.stdin,
                output=sys.stdout,
            )
            # Persist ring-buffer history.
            if install is not None:
                history_cmds = _parse_history(raw_history)
                if history_cmds:
                    store.save_command_history(db, install.id, history_cmds)
        else:
            # Uninstall path.
            removed_at = datetime.now(UTC).isoformat()
            capture_removal(
                db,
                command_str=command,
                work_dir=cwd,
                removed_at=removed_at,
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
