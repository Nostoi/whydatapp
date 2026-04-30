from __future__ import annotations

import pytest

from why.detect import match_install, MatchResult


@pytest.mark.parametrize("cmd,manager,pkgs", [
    ("brew install ripgrep", "brew", ["ripgrep"]),
    ("brew install ripgrep fd", "brew", ["ripgrep", "fd"]),
    ("npm install -g typescript", "npm", ["typescript"]),
    ("npm i -g typescript prettier", "npm", ["typescript", "prettier"]),
    ("npm install --global eslint", "npm", ["eslint"]),
    ("pnpm add -g pnpm-bin", "pnpm", ["pnpm-bin"]),
    ("yarn global add nodemon", "yarn", ["nodemon"]),
    ("bun add -g zx", "bun", ["zx"]),
    ("pip install httpx", "pip", ["httpx"]),
    ("pip3 install requests urllib3", "pip", ["requests", "urllib3"]),
    ("pipx install black", "pipx", ["black"]),
    ("uv tool install ruff", "uv", ["ruff"]),
    ("cargo install ripgrep", "cargo", ["ripgrep"]),
    ("git clone https://github.com/foo/bar", "git", ["bar"]),
    ("git clone https://github.com/foo/bar.git baz", "git", ["baz"]),
])
def test_matches_tier1(cmd: str, manager: str, pkgs: list[str]) -> None:
    m = match_install(cmd)
    assert m is not None
    assert m.manager == manager
    assert m.packages == pkgs


@pytest.mark.parametrize("cmd", [
    "ls -la",
    "echo hello",
    "npm install",
    "pnpm install",
    "yarn",
    "pip install -r requirements.txt",
    "pip install -e .",
    "cargo build",
    "bundle install",
    "git pull",
    "brew update",
    "npm install lodash",
])
def test_no_match_for_non_install_or_dependency_restore(cmd: str) -> None:
    assert match_install(cmd) is None


from why.detect import IgnoreContext, should_ignore


def _ctx(**kw) -> IgnoreContext:
    base = dict(
        command="brew install ripgrep",
        cwd="/tmp",
        exit_code=0,
        interactive=True,
        suppress_env=False,
        parent_process_name=None,
        recent_duplicate=False,
        user_ignore_patterns=(),
    )
    base.update(kw)
    return IgnoreContext(**base)


def test_ignore_when_exit_nonzero():
    assert should_ignore(_ctx(exit_code=1))


def test_ignore_when_non_interactive():
    assert should_ignore(_ctx(interactive=False))


def test_ignore_when_suppress_env():
    assert should_ignore(_ctx(suppress_env=True))


def test_ignore_when_parent_is_tracked_installer():
    assert should_ignore(_ctx(parent_process_name="brew"))
    assert should_ignore(_ctx(parent_process_name="cargo"))


def test_ignore_when_recent_duplicate():
    assert should_ignore(_ctx(recent_duplicate=True))


def test_ignore_when_user_pattern_matches():
    assert should_ignore(_ctx(user_ignore_patterns=(r"^brew\s+install\s+ripgrep$",)))


def test_does_not_ignore_normal_case():
    assert not should_ignore(_ctx())
