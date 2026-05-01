from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from why.cli import app
from why.shells.installer import (
    BLOCK_BEGIN,
    BLOCK_END,
    detect_shell,
    install_into_rc,
    rc_file_for,
    remove_from_rc,
)

cli_runner = CliRunner()


def test_install_appends_block_with_fence(tmp_path: Path):
    rc = tmp_path / ".zshrc"
    rc.write_text("# existing\n")
    install_into_rc(rc, hook_path=Path("/x/hook.zsh"))
    text = rc.read_text()
    assert BLOCK_BEGIN in text
    assert BLOCK_END in text
    assert "/x/hook.zsh" in text


def test_install_is_idempotent(tmp_path: Path):
    rc = tmp_path / ".zshrc"
    rc.write_text("")
    install_into_rc(rc, hook_path=Path("/x/hook.zsh"))
    install_into_rc(rc, hook_path=Path("/x/hook.zsh"))
    assert rc.read_text().count(BLOCK_BEGIN) == 1


def test_remove_strips_block(tmp_path: Path):
    rc = tmp_path / ".zshrc"
    rc.write_text("before\n")
    install_into_rc(rc, hook_path=Path("/x/hook.zsh"))
    rc.write_text(rc.read_text() + "after\n")
    remove_from_rc(rc)
    text = rc.read_text()
    assert "before" in text
    assert "after" in text
    assert BLOCK_BEGIN not in text
    assert BLOCK_END not in text


def test_detect_shell_from_env(monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/zsh")
    assert detect_shell() == "zsh"
    monkeypatch.setenv("SHELL", "/usr/local/bin/bash")
    assert detect_shell() == "bash"
    monkeypatch.setenv("SHELL", "/opt/homebrew/bin/fish")
    assert detect_shell() == "fish"


def test_rc_file_for_returns_expected_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert rc_file_for("zsh") == tmp_path / ".zshrc"
    assert rc_file_for("bash") == tmp_path / ".bashrc"
    assert rc_file_for("fish") == tmp_path / ".config/fish/config.fish"


def test_uninstall_removes_block_and_keeps_data(tmp_path: Path, why_home: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SHELL", "/bin/zsh")
    rc = tmp_path / ".zshrc"
    rc.write_text("# x\n")
    init_answers = "\n".join(
        ["lab"] + ["y"]*11 + ["n", "", "n", "y"]
    ) + "\n"
    cli_runner.invoke(app, ["init"], input=init_answers)
    assert BLOCK_BEGIN in rc.read_text()

    result = cli_runner.invoke(app, ["uninstall"], input="n\n")
    assert result.exit_code == 0
    assert BLOCK_BEGIN not in rc.read_text()
    assert (why_home / "data.db").exists()


def test_uninstall_removes_data_when_confirmed(tmp_path: Path, why_home: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SHELL", "/bin/zsh")
    rc = tmp_path / ".zshrc"
    rc.write_text("")
    init_answers = "\n".join(
        ["lab"] + ["y"]*11 + ["n", "", "n", "y"]
    ) + "\n"
    cli_runner.invoke(app, ["init"], input=init_answers)

    result = cli_runner.invoke(app, ["uninstall"], input="y\n")
    assert result.exit_code == 0
    assert not (why_home / "data.db").exists()
