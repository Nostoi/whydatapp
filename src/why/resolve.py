from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _run(args: list[str], timeout: float = 2.0) -> str | None:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


def _resolve_brew(pkg: str) -> str | None:
    return _run(["brew", "--prefix", pkg])


def _resolve_cargo(pkg: str) -> str | None:
    home = os.environ.get("CARGO_HOME") or str(Path.home() / ".cargo")
    candidate = Path(home) / "bin" / pkg
    return str(candidate) if candidate.exists() else None


def _resolve_pipx(pkg: str) -> str | None:
    home = Path.home() / ".local/share/pipx/venvs" / pkg
    return str(home) if home.exists() else None


def _resolve_uv_tool(pkg: str) -> str | None:
    base = Path.home() / ".local/share/uv/tools" / pkg
    return str(base) if base.exists() else None


def _resolve_npm_global(pkg: str) -> str | None:
    root = _run(["npm", "root", "-g"])
    if not root:
        return None
    candidate = Path(root) / pkg
    return str(candidate) if candidate.exists() else None


def _resolve_git(pkg: str, cwd: str) -> str | None:
    candidate = Path(cwd) / pkg
    return str(candidate) if candidate.exists() else None


def resolve_path(*, manager: str, package: str, cwd: str) -> str | None:
    """Best-effort resolution of where the install landed. Never raises."""
    try:
        match manager:
            case "brew":
                return _resolve_brew(package)
            case "cargo":
                return _resolve_cargo(package)
            case "pipx":
                return _resolve_pipx(package)
            case "uv":
                return _resolve_uv_tool(package)
            case "npm" | "pnpm" | "yarn" | "bun":
                return _resolve_npm_global(package)
            case "git":
                return _resolve_git(package, cwd)
            case _:
                return None
    except Exception:
        return None
