from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from why.cli import app
from why.shells.installer import BLOCK_BEGIN

runner = CliRunner()


def test_init_creates_home_and_rc_block(why_home: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SHELL", "/bin/zsh")
    rc = tmp_path / ".zshrc"
    rc.write_text("# existing\n")
    answers = "\n".join([
        "work-mbp",
        "y", "y", "y", "y", "y", "y", "y", "y", "y", "y",
        "n",
        "",
        "n",
        "y",
    ]) + "\n"
    result = runner.invoke(app, ["init"], input=answers)
    assert result.exit_code == 0, result.stdout
    assert (why_home / "config.toml").exists()
    assert (why_home / "data.db").exists()
    assert (why_home / "hook.zsh").exists()
    assert BLOCK_BEGIN in rc.read_text()
