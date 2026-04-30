from __future__ import annotations

import re
import shlex
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


_HEAD = {
    "brew":  ("brew",  _extract_brew),
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
        if len(tokens) < 3 or tokens[1] != "install":
            return None
        pkgs = extractor(tokens)
        if not pkgs:
            return None
        return MatchResult(manager=manager, packages=pkgs)
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
    suppress_env: bool
    parent_process_name: str | None
    recent_duplicate: bool
    user_ignore_patterns: tuple[str, ...]


def should_ignore(ctx: IgnoreContext) -> bool:
    if ctx.exit_code != 0:
        return True
    if not ctx.interactive:
        return True
    if ctx.suppress_env:
        return True
    if ctx.parent_process_name and ctx.parent_process_name in IGNORED_PARENTS:
        return True
    if ctx.recent_duplicate:
        return True
    for p in ctx.user_ignore_patterns:
        if re.search(p, ctx.command):
            return True
    return False
