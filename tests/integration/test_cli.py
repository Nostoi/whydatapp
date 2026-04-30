from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from why.cli import app

runner = CliRunner()


def test_version_command(why_home: Path) -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "why" in result.stdout


def test_list_command_on_empty_db(why_home: Path) -> None:
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No installs" in result.stdout


def test_log_records_install_with_interactive_input(why_home: Path) -> None:
    answers = "\n".join(["1", "ripgrep", "fast grep", "whydatapp", "speed", ""]) + "\n"
    result = runner.invoke(
        app, ["log", "--", "brew", "install", "ripgrep"], input=answers
    )
    assert result.exit_code == 0
    listed = runner.invoke(app, ["list"])
    assert "ripgrep" in listed.stdout
    assert "doc" in listed.stdout


def test_log_skip_creates_incomplete_entry(why_home: Path) -> None:
    result = runner.invoke(app, ["log", "--", "brew", "install", "fd"], input="s\n")
    assert result.exit_code == 0
    listed = runner.invoke(app, ["list", "--incomplete"])
    assert "fd" in listed.stdout


def test_log_rejects_non_install_command(why_home: Path) -> None:
    result = runner.invoke(app, ["log", "--", "ls", "-la"])
    assert result.exit_code != 0
    assert "not recognized" in result.stdout.lower()
