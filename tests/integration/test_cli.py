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


def test_review_drains_skipped(why_home: Path) -> None:
    runner.invoke(app, ["log", "--", "brew", "install", "ripgrep"], input="s\n")
    answers = "\n".join(["1", "ripgrep", "grep", "p", "speed", ""]) + "\n"
    result = runner.invoke(app, ["review"], input=answers)
    assert result.exit_code == 0
    listed = runner.invoke(app, ["list", "--incomplete"])
    assert "ripgrep" not in listed.stdout


def test_export_json(why_home: Path, tmp_path: Path) -> None:
    answers = "\n".join(["1", "ripgrep", "grep", "p", "speed", ""]) + "\n"
    runner.invoke(app, ["log", "--", "brew", "install", "ripgrep"], input=answers)
    out = tmp_path / "out.json"
    result = runner.invoke(app, ["export", "--format", "json", "--out", str(out)])
    assert result.exit_code == 0
    text = out.read_text()
    assert "ripgrep" in text
    assert "\"disposition\": \"doc\"" in text


def test_delete_soft(why_home: Path) -> None:
    answers = "\n".join(["1", "rg", "g", "p", "w", ""]) + "\n"
    runner.invoke(app, ["log", "--", "brew", "install", "ripgrep"], input=answers)
    result = runner.invoke(app, ["delete", "1", "--yes"])
    assert result.exit_code == 0
    listed_after = runner.invoke(app, ["list"])
    assert "ripgrep" not in listed_after.stdout


def test_hook_no_match_silent(why_home: Path) -> None:
    result = runner.invoke(app, ["_hook", "--cmd", "ls -la", "--cwd", "/tmp", "--code", "0"])
    assert result.exit_code == 0
    assert result.stdout == ""


def test_hook_nonzero_exit_silent(why_home: Path) -> None:
    result = runner.invoke(
        app, ["_hook", "--cmd", "brew install x", "--cwd", "/tmp", "--code", "1"]
    )
    assert result.exit_code == 0
    assert result.stdout == ""


def test_hook_matched_runs_prompt(why_home: Path, monkeypatch) -> None:
    monkeypatch.setenv("WHY_HOOK_FORCE_PROMPT", "1")
    answers = "\n".join(["1", "ripgrep", "g", "p", "w", ""]) + "\n"
    result = runner.invoke(
        app,
        ["_hook", "--cmd", "brew install ripgrep", "--cwd", "/tmp", "--code", "0"],
        input=answers,
    )
    assert result.exit_code == 0
    listed = runner.invoke(app, ["list"])
    assert "ripgrep" in listed.stdout


def test_serve_invokes_uvicorn(monkeypatch, why_home: Path) -> None:
    called = {}

    def fake_run(app, **kw):
        called["host"] = kw.get("host")
        called["port"] = kw.get("port")

    import uvicorn
    monkeypatch.setattr(uvicorn, "run", fake_run)
    monkeypatch.setattr("webbrowser.open", lambda *a, **kw: None)
    result = runner.invoke(app, ["serve", "--no-open"])
    assert result.exit_code == 0
    assert called["host"] == "127.0.0.1"
    assert called["port"] == 7873
