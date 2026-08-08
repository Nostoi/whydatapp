"""The CLI refreshes a stale shell hook and says so — but only where it's safe.

The notice goes to stderr: `why export` writes markdown to stdout and
`why follow status --porcelain` is machine-parsed, so stdout must stay clean.
Both streams land on the same tty, so the user still sees it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from why.cli import app
from why.shells.installer import packaged_hook_version

runner = CliRunner()


def _stale(why_home: Path, shell: str = "zsh") -> Path:
    target = why_home / f"hook.{shell}"
    target.write_text("WHY_HOOK_VERSION=1\n_why_precmd() { :; }\n")
    return target


def test_user_facing_command_refreshes_and_announces(why_home: Path) -> None:
    target = _stale(why_home)

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "WHY_HOOK_VERSION=1" not in target.read_text()
    assert f"v1 → v{packaged_hook_version('zsh')}" in result.stderr
    assert "exec $SHELL -l" in result.stderr
    assert "shell hook" not in result.stdout


def test_notice_is_silent_when_the_hook_is_current(why_home: Path) -> None:
    from why.shells.installer import copy_hook_to_home

    copy_hook_to_home("zsh", why_home)

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "shell hook" not in result.stderr


def test_notice_is_silent_when_no_hook_is_installed(why_home: Path) -> None:
    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "shell hook" not in result.stderr
    assert not (why_home / "hook.zsh").exists()


@pytest.mark.parametrize(
    "argv",
    [
        ["_record", "--cmd", "ls", "--cwd", "/tmp", "--code", "0"],
        ["_hook", "--cmd", "ls", "--cwd", "/tmp", "--code", "0"],
    ],
)
def test_prompt_cycle_commands_never_print_the_notice(
    why_home: Path, argv: list[str]
) -> None:
    """These run inside the shell's precmd; printing there corrupts the terminal."""
    target = _stale(why_home)

    result = runner.invoke(app, argv)

    assert result.exit_code == 0
    assert result.stdout == ""
    assert "shell hook" not in result.stderr
    assert target.read_text().startswith("WHY_HOOK_VERSION=1")


def test_why_suppress_silences_the_notice(
    why_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hook sets WHY_SUPPRESS=1 on everything it invokes, including
    `why follow status` — which is a normal, non-hidden command."""
    monkeypatch.setenv("WHY_SUPPRESS", "1")
    target = _stale(why_home)

    result = runner.invoke(app, ["follow", "status"])

    assert "shell hook" not in result.stderr
    assert target.read_text().startswith("WHY_HOOK_VERSION=1")


def test_init_does_not_double_announce(why_home: Path) -> None:
    """`why init` rewrites the hook itself; a stale-hook notice first is noise."""
    _stale(why_home)

    result = runner.invoke(app, ["init"], input="\n")

    assert "shell hook updated" not in result.stderr
