"""Tests for match_uninstall in detect.py."""
from __future__ import annotations

import pytest

from why.detect import match_uninstall


@pytest.mark.parametrize("cmd,manager,pkg", [
    ("brew uninstall ripgrep", "brew", "ripgrep"),
    ("brew remove ripgrep", "brew", "ripgrep"),
    ("brew rm ripgrep", "brew", "ripgrep"),
    ("npm uninstall -g typescript", "npm", "typescript"),
    ("npm remove -g typescript", "npm", "typescript"),
    ("npm rm --global typescript", "npm", "typescript"),
    ("pnpm remove --global prettier", "pnpm", "prettier"),
    ("pnpm rm -g prettier", "pnpm", "prettier"),
    ("yarn global remove lodash", "yarn", "lodash"),
    ("bun remove -g nodemon", "bun", "nodemon"),
    ("pip uninstall requests", "pip", "requests"),
    ("pip3 uninstall requests", "pip", "requests"),
    ("pipx uninstall black", "pipx", "black"),
    ("uv tool uninstall ruff", "uv", "ruff"),
    ("cargo uninstall ripgrep", "cargo", "ripgrep"),
])
def test_match_uninstall_tier1(cmd: str, manager: str, pkg: str) -> None:
    result = match_uninstall(cmd)
    assert result is not None, f"expected match for: {cmd!r}"
    assert result.manager == manager
    assert result.packages[0] == pkg


@pytest.mark.parametrize("cmd", [
    "brew install ripgrep",        # install, not uninstall
    "brew uninstall",              # missing package
    "npm uninstall typescript",    # missing -g flag
    "pip uninstall -r req.txt",    # requirement file flag
    "git clone https://x.com/r",  # git has no uninstall
    "gh repo clone user/repo",    # gh has no uninstall
    "not a real command",
    "",
])
def test_match_uninstall_negative(cmd: str) -> None:
    assert match_uninstall(cmd) is None, f"unexpected match for: {cmd!r}"
