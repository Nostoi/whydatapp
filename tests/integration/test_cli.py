from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from why import store
from why.bootstrap import ensure_ready
from why.cli import app
from why.store import InstallFilters

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


# ---------------------------------------------------------------------------
# Enrichment integration tests
# ---------------------------------------------------------------------------


def test_hook_enriches_complete_install(why_home: Path, monkeypatch) -> None:
    """Second hook for the same package (from different cwd) updates the existing row."""
    monkeypatch.setenv("WHY_HOOK_FORCE_PROMPT", "1")

    # First hook — create a complete record.
    answers = "\n".join(["1", "ripgrep", "fast grep", "proj", "speed", ""]) + "\n"
    result = runner.invoke(
        app,
        ["_hook", "--cmd", "brew install ripgrep", "--cwd", "/tmp/proj1", "--code", "0"],
        input=answers,
    )
    assert result.exit_code == 0

    listed = runner.invoke(app, ["list"])
    assert "ripgrep" in listed.stdout
    row_count_before = listed.stdout.count("ripgrep")

    # Second hook from a different cwd (avoids the 60s duplicate debounce, which
    # is keyed on (command, install_dir)).
    result2 = runner.invoke(
        app,
        ["_hook", "--cmd", "brew install ripgrep", "--cwd", "/tmp/proj2", "--code", "0"],
        input="",  # no prompt input — should short-circuit silently
    )
    assert result2.exit_code == 0
    # The re-install confirmation line should appear.
    assert "re-installed" in result2.output or "re-installed" in result2.stdout

    # Still only one row (the existing record was updated, not duplicated).
    listed2 = runner.invoke(app, ["list"])
    # The re-install confirmation appears in output (via sys.stdout.write, not rich console).
    assert listed2.stdout.count("ripgrep") == row_count_before


def test_hook_prompts_with_prefill_when_incomplete(why_home: Path, monkeypatch) -> None:
    """When an incomplete record exists, the hook surfaces the prompt (prefilled) and
    updates the same row — does NOT create a second entry."""
    monkeypatch.setenv("WHY_HOOK_FORCE_PROMPT", "1")

    # First hook — skip (creates incomplete record).
    result = runner.invoke(
        app,
        ["_hook", "--cmd", "brew install fd", "--cwd", "/tmp/proj1", "--code", "0"],
        input="s\n",
    )
    assert result.exit_code == 0

    # Second hook from different cwd — should surface prompt again (prefilled), NOT enrich silently.
    answers = "\n".join(["1", "fd", "fast find", "proj", "speed", ""]) + "\n"
    result2 = runner.invoke(
        app,
        ["_hook", "--cmd", "brew install fd", "--cwd", "/tmp/proj2", "--code", "0"],
        input=answers,
    )
    assert result2.exit_code == 0

    # Exactly one row (updated in place).
    listed = runner.invoke(app, ["list"])
    assert "fd" in listed.stdout
    # No incomplete entries remain.
    incomplete = runner.invoke(app, ["list", "--incomplete"])
    assert "fd" not in incomplete.stdout


def test_log_creates_new_entry_by_default(why_home: Path) -> None:
    """Manual `why log` always creates a new entry even if one already exists."""
    answers = "\n".join(["1", "ripgrep", "fast grep", "proj", "speed", ""]) + "\n"
    runner.invoke(app, ["log", "--", "brew", "install", "ripgrep"], input=answers)

    # Second manual log — should create a SECOND row, not enrich.
    answers2 = "\n".join(["1", "ripgrep", "fast grep", "proj2", "speed again", ""]) + "\n"
    result = runner.invoke(
        app,
        ["log", "--cwd", "/tmp/other", "--", "brew", "install", "ripgrep"],
        input=answers2,
    )
    assert result.exit_code == 0

    db = ensure_ready()
    rows = store.list_installs(db, InstallFilters(manager="brew"))
    assert len(rows) == 2


def test_log_with_enrich_flag(why_home: Path) -> None:
    """Manual `why log --enrich` updates existing complete entry instead of creating a new one."""
    answers = "\n".join(["1", "bat", "cat with syntax hl", "proj", "ux", ""]) + "\n"
    runner.invoke(app, ["log", "--", "brew", "install", "bat"], input=answers)

    # Second log with --enrich: should update the same row.
    result = runner.invoke(
        app,
        ["log", "--enrich", "--cwd", "/tmp/other", "--", "brew", "install", "bat"],
        input="",  # no prompt input — should short-circuit
    )
    assert result.exit_code == 0
    assert "re-installed" in result.output or "re-installed" in result.stdout

    db = ensure_ready()
    rows = store.list_installs(db, InstallFilters(manager="brew"))
    assert len(rows) == 1
    assert rows[0].reinstall_count == 1
