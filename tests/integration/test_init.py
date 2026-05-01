from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from why import init_wizard
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
        "y", "y", "y", "y", "y", "y", "y", "y", "y", "y", "y",
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


def test_offer_shell_reload_skips_when_not_a_tty(monkeypatch):
    """CI / scripted runs (no TTY) must never prompt or exec."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)

    called = {"exec": False}

    def fake_exec(*a, **kw):
        called["exec"] = True

    monkeypatch.setattr("os.execvp", fake_exec)

    from rich.console import Console
    init_wizard._offer_shell_reload(Console())
    assert called["exec"] is False


def test_offer_shell_reload_skips_with_env_escape(monkeypatch):
    """WHY_INIT_NO_RELOAD=1 disables the prompt even on an interactive TTY."""
    monkeypatch.setenv("WHY_INIT_NO_RELOAD", "1")
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("SHELL", "/bin/zsh")

    called = {"exec": False, "confirm": False}
    monkeypatch.setattr("os.execvp", lambda *a, **kw: called.__setitem__("exec", True))
    monkeypatch.setattr(
        "typer.confirm", lambda *a, **kw: (called.__setitem__("confirm", True) or True)
    )

    from rich.console import Console
    init_wizard._offer_shell_reload(Console())
    assert called == {"exec": False, "confirm": False}


def test_offer_shell_reload_declines_does_not_exec(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("SHELL", "/bin/zsh")
    monkeypatch.delenv("WHY_INIT_NO_RELOAD", raising=False)
    monkeypatch.setattr("os.path.exists", lambda p: True)

    called = {"exec": False}
    monkeypatch.setattr("os.execvp", lambda *a, **kw: called.__setitem__("exec", True))
    monkeypatch.setattr("typer.confirm", lambda *a, **kw: False)

    from rich.console import Console
    init_wizard._offer_shell_reload(Console())
    assert called["exec"] is False


def test_offer_shell_reload_accepts_calls_execvp(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("SHELL", "/bin/zsh")
    monkeypatch.delenv("WHY_INIT_NO_RELOAD", raising=False)
    monkeypatch.setattr("os.path.exists", lambda p: True)

    captured: dict[str, object] = {}

    def fake_exec(file, args):
        captured["file"] = file
        captured["args"] = args

    monkeypatch.setattr("os.execvp", fake_exec)
    monkeypatch.setattr("typer.confirm", lambda *a, **kw: True)

    from rich.console import Console
    init_wizard._offer_shell_reload(Console())
    assert captured["file"] == "/bin/zsh"
    assert captured["args"] == ["/bin/zsh", "-l"]


def test_offer_shell_reload_handles_exec_failure(monkeypatch):
    """If execvp raises, the wizard must not crash — fall back to the
    standard 'restart your shell' message."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("SHELL", "/bin/zsh")
    monkeypatch.delenv("WHY_INIT_NO_RELOAD", raising=False)
    monkeypatch.setattr("os.path.exists", lambda p: True)

    def boom(*a, **kw):
        raise OSError("simulated exec failure")

    monkeypatch.setattr("os.execvp", boom)
    monkeypatch.setattr("typer.confirm", lambda *a, **kw: True)

    from rich.console import Console
    init_wizard._offer_shell_reload(Console())  # must not raise


# Suppress unused-import lint warning; pytest is imported for fixture typing
# in the existing test above.
_ = pytest
