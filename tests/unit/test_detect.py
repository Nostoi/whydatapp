from __future__ import annotations

import pytest

from why.detect import IgnoreContext, is_self_or_source_install, match_install, should_ignore


@pytest.mark.parametrize("cmd,manager,pkgs", [
    ("brew install ripgrep", "brew", ["ripgrep"]),
    ("brew install ripgrep fd", "brew", ["ripgrep", "fd"]),
    ("brew reinstall ripgrep", "brew", ["ripgrep"]),
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
    ("gh repo clone 0x0funky/agent-sprite-forge", "gh", ["agent-sprite-forge"]),
    ("gh repo clone 0x0funky/agent-sprite-forge my-fork", "gh", ["my-fork"]),
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



@pytest.mark.parametrize("cmd", [
    "uv tool install --editable '.[web]'",
    "uv tool install --editable .",
    "uv tool install why-cli",
    "uv tool install 'why-cli[web]'",
    "pipx install why-cli",
    "pipx install --editable .",
    "pip install ./dist/why_cli-1.2.0-py3-none-any.whl",
    "pip install /Users/me/projects/whydatapp",
    "pip install git+https://github.com/Nostoi/whydatapp",
    "uv tool install whydatapp",
    "uv tool install WHY_CLI",
])
def test_self_or_source_installs_are_dropped(cmd):
    assert match_install(cmd) is None, f"should drop self/source install: {cmd}"


def test_is_self_or_source_install_helper_direct():
    assert is_self_or_source_install("uv", [".[web]"])
    assert is_self_or_source_install("pip", ["/absolute/path"])
    assert is_self_or_source_install("pipx", ["why-cli"])
    assert is_self_or_source_install("cargo", ["why_cli"])
    assert not is_self_or_source_install("uv", ["ruff"])
    assert not is_self_or_source_install("brew", [".[web]"])  # brew not in filter set


def test_why_no_self_log_escape_hatch(monkeypatch):
    monkeypatch.setenv("WHY_NO_SELF_LOG", "1")
    # Even a normal install returns True (should be dropped) when env is set
    assert is_self_or_source_install("uv", ["ruff"])


def _ctx(**kw) -> IgnoreContext:
    base = dict(
        command="brew install ripgrep",
        cwd="/tmp",
        exit_code=0,
        interactive=True,
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


def test_hook_does_not_self_ignore_when_why_suppress_set(monkeypatch):
    """Regression: the shell hook calls 'WHY_SUPPRESS=1 why _hook ...' as
    a shell-level recursion guard. Python must not interpret WHY_SUPPRESS
    in its own environment as 'ignore me' — that silently cancelled
    every capture in 1.0.x and 1.1.0."""
    monkeypatch.setenv("WHY_SUPPRESS", "1")
    monkeypatch.setenv("WHY_HOOK_FORCE_PROMPT", "1")
    # If a future caller adds back a WHY_SUPPRESS check, this normal
    # context (which omits any suppress_env field) must remain non-ignored.
    assert not should_ignore(_ctx())


def test_ignore_when_parent_is_tracked_installer():
    assert should_ignore(_ctx(parent_process_name="brew"))
    assert should_ignore(_ctx(parent_process_name="cargo"))


def test_ignore_when_recent_duplicate():
    assert should_ignore(_ctx(recent_duplicate=True))


def test_ignore_when_user_pattern_matches():
    assert should_ignore(_ctx(user_ignore_patterns=(r"^brew\s+install\s+ripgrep$",)))


def test_does_not_ignore_normal_case():
    assert not should_ignore(_ctx())
