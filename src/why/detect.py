from __future__ import annotations

import os
import re
import shlex
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class MatchResult:
    manager: str
    packages: list[str]


_GLOBAL_NPM = re.compile(r"^(-g|--global)$")


def _strip_flags(tokens: list[str]) -> list[str]:
    return [t for t in tokens if not t.startswith("-")]


def _extract_brew(tokens: list[str]) -> list[str]:
    return _strip_flags(tokens[2:])


def _extract_npm_global(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 4:
        return None
    if tokens[1] not in ("install", "i"):
        return None
    if not any(_GLOBAL_NPM.match(t) for t in tokens[2:]):
        return None
    pkgs = _strip_flags(tokens[2:])
    return pkgs or None


def _extract_pnpm(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 4 or tokens[1] != "add":
        return None
    if not any(t in ("-g", "--global") for t in tokens[2:]):
        return None
    return _strip_flags(tokens[2:]) or None


def _extract_yarn(tokens: list[str]) -> list[str] | None:
    if len(tokens) >= 4 and tokens[1] == "global" and tokens[2] == "add":
        return _strip_flags(tokens[3:]) or None
    return None


def _extract_bun(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 4 or tokens[1] != "add":
        return None
    if not any(t in ("-g", "--global") for t in tokens[2:]):
        return None
    return _strip_flags(tokens[2:]) or None


def _extract_pip(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 3 or tokens[1] != "install":
        return None
    if any(t in ("-r", "--requirement", "-e", "--editable") for t in tokens[2:]):
        return None
    pkgs = _strip_flags(tokens[2:])
    return pkgs or None


def _extract_pipx(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 3 or tokens[1] != "install":
        return None
    return _strip_flags(tokens[2:]) or None


def _extract_uv_tool(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 4 or tokens[1] != "tool" or tokens[2] != "install":
        return None
    return _strip_flags(tokens[3:]) or None


def _extract_cargo(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 3 or tokens[1] != "install":
        return None
    return _strip_flags(tokens[2:]) or None


def _extract_git_clone(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 3 or tokens[1] != "clone":
        return None
    args = _strip_flags(tokens[2:])
    if not args:
        return None
    if len(args) >= 2:
        return [args[1]]
    url = args[0]
    name = url.rstrip("/").rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return [name] if name else None


def _extract_gh_clone(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 4 or tokens[1] != "repo" or tokens[2] != "clone":
        return None
    args = _strip_flags(tokens[3:])
    if not args:
        return None
    if len(args) >= 2:
        return [args[1]]
    ref = args[0]
    name = ref.rsplit("/", 1)[-1]
    return [name] if name else None


_HEAD = {
    "brew":  ("brew",  _extract_brew),
    "gh":    ("gh",    _extract_gh_clone),
    "npm":   ("npm",   _extract_npm_global),
    "pnpm":  ("pnpm",  _extract_pnpm),
    "yarn":  ("yarn",  _extract_yarn),
    "bun":   ("bun",   _extract_bun),
    "pip":   ("pip",   _extract_pip),
    "pip3":  ("pip",   _extract_pip),
    "pipx":  ("pipx",  _extract_pipx),
    "uv":    ("uv",    _extract_uv_tool),
    "cargo": ("cargo", _extract_cargo),
    "git":   ("git",   _extract_git_clone),
}


# ---------------------------------------------------------------------------
# Uninstall extractors
# ---------------------------------------------------------------------------

def _extract_brew_uninstall(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 3 or tokens[1] not in ("uninstall", "remove", "rm"):
        return None
    return _strip_flags(tokens[2:]) or None


def _extract_npm_uninstall(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 4:
        return None
    if tokens[1] not in ("uninstall", "remove", "rm", "r", "un"):
        return None
    if not any(_GLOBAL_NPM.match(t) for t in tokens[2:]):
        return None
    return _strip_flags(tokens[2:]) or None


def _extract_pnpm_uninstall(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 4:
        return None
    if tokens[1] not in ("remove", "rm", "uninstall", "un"):
        return None
    if not any(t in ("-g", "--global") for t in tokens[2:]):
        return None
    return _strip_flags(tokens[2:]) or None


def _extract_yarn_uninstall(tokens: list[str]) -> list[str] | None:
    if len(tokens) >= 4 and tokens[1] == "global" and tokens[2] == "remove":
        return _strip_flags(tokens[3:]) or None
    return None


def _extract_bun_uninstall(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 4:
        return None
    if tokens[1] not in ("remove", "rm"):
        return None
    if not any(t in ("-g", "--global") for t in tokens[2:]):
        return None
    return _strip_flags(tokens[2:]) or None


def _extract_pip_uninstall(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 3 or tokens[1] != "uninstall":
        return None
    if any(t in ("-r", "--requirement") for t in tokens[2:]):
        return None
    return _strip_flags(tokens[2:]) or None


def _extract_pipx_uninstall(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 3 or tokens[1] != "uninstall":
        return None
    return _strip_flags(tokens[2:]) or None


def _extract_uv_tool_uninstall(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 4 or tokens[1] != "tool" or tokens[2] != "uninstall":
        return None
    return _strip_flags(tokens[3:]) or None


def _extract_cargo_uninstall(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 3 or tokens[1] != "uninstall":
        return None
    return _strip_flags(tokens[2:]) or None


# Maps CLI head → (manager_name, extractor) for uninstall commands.
# git and gh are omitted — they have no meaningful uninstall concept.
_UNINSTALL_HEAD: dict[str, tuple[str, Callable[[list[str]], list[str] | None]]] = {
    "brew":  ("brew",  _extract_brew_uninstall),
    "npm":   ("npm",   _extract_npm_uninstall),
    "pnpm":  ("pnpm",  _extract_pnpm_uninstall),
    "yarn":  ("yarn",  _extract_yarn_uninstall),
    "bun":   ("bun",   _extract_bun_uninstall),
    "pip":   ("pip",   _extract_pip_uninstall),
    "pip3":  ("pip",   _extract_pip_uninstall),
    "pipx":  ("pipx",  _extract_pipx_uninstall),
    "uv":    ("uv",    _extract_uv_tool_uninstall),
    "cargo": ("cargo", _extract_cargo_uninstall),
}


_SELF_NAMES = frozenset({"why-cli", "why_cli", "whydatapp"})

# Managers where self/source-install filtering applies
_SELF_FILTER_MANAGERS = frozenset({"uv", "pipx", "pip", "cargo"})


def is_self_or_source_install(manager: str, packages: list[str]) -> bool:
    """Return True if this install should be filtered out as a self or source install.

    Filters:
    - Local path args (starting with `.`, `/`, or containing `[` like `.[web]`)
    - Wheel or tarball filenames
    - git+ URLs
    - Package names matching whydatApp itself (why-cli, why_cli, whydatapp)
    - WHY_NO_SELF_LOG=1 env escape hatch (drops all captures from this function)
    """
    if os.environ.get("WHY_NO_SELF_LOG") == "1":
        return True
    if manager not in _SELF_FILTER_MANAGERS:
        return False
    if not packages:
        return False
    first = packages[0]
    # Local path checks
    if first.startswith(".") or first.startswith("/"):
        return True
    if "[" in first:
        return True
    # Wheel or tarball
    if first.endswith(".whl") or first.endswith(".tar.gz") or first.endswith(".tgz"):
        return True
    # git+ URL
    if first.startswith("git+"):
        return True
    # Self-name check (case-insensitive, normalized)
    normalized = first.lower().split("[")[0]  # strip extras like ruff[fix]
    return normalized in _SELF_NAMES


def match_install(command: str) -> MatchResult | None:
    """Return a MatchResult if the command is a user-intent install. Else None."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    if not tokens:
        return None
    head = tokens[0].rsplit("/", 1)[-1]
    rule = _HEAD.get(head)
    if not rule:
        return None
    manager, extractor = rule
    if head == "brew":
        if len(tokens) < 3 or tokens[1] not in ("install", "reinstall"):
            return None
        pkgs = extractor(tokens)
        if not pkgs:
            return None
        return MatchResult(manager=manager, packages=pkgs)
    pkgs = extractor(tokens)
    if not pkgs:
        return None
    if is_self_or_source_install(manager, pkgs):
        return None
    return MatchResult(manager=manager, packages=pkgs)


def match_uninstall(command: str) -> MatchResult | None:
    """Return a MatchResult if the command is a user-intent uninstall. Else None."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    if not tokens:
        return None
    head = tokens[0].rsplit("/", 1)[-1]
    rule = _UNINSTALL_HEAD.get(head)
    if not rule:
        return None
    manager, extractor = rule
    pkgs = extractor(tokens)
    if not pkgs:
        return None
    return MatchResult(manager=manager, packages=pkgs)


IGNORED_PARENTS = frozenset({
    "brew", "pip", "pip3", "npm", "pnpm", "yarn", "bun", "cargo", "make",
    "docker", "nix", "asdf", "mise", "volta", "nvm", "why",
})


@dataclass(frozen=True)
class IgnoreContext:
    command: str
    cwd: str
    exit_code: int
    interactive: bool
    parent_process_name: str | None
    recent_duplicate: bool
    user_ignore_patterns: tuple[str, ...]


def should_ignore(ctx: IgnoreContext) -> bool:
    if ctx.exit_code != 0:
        return True
    if not ctx.interactive:
        return True
    if ctx.parent_process_name and ctx.parent_process_name in IGNORED_PARENTS:
        return True
    if ctx.recent_duplicate:
        return True
    return any(re.search(p, ctx.command) for p in ctx.user_ignore_patterns)
