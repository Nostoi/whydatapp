"""Tests for capture_removal and prompt_removal."""
from __future__ import annotations

import io
from pathlib import Path

from why import store
from why.capture import capture_removal
from why.prompts import prompt_removal
from why.schema import migrate


def _db(tmp_path: Path) -> Path:
    p = tmp_path / "data.db"
    migrate(p)
    return p


def _user_device(db: Path) -> tuple[str, str]:
    user = store.get_solo_user(db) or store.create_user(db, display_name="t")
    device = store.get_solo_device(db) or store.create_device(db, hostname="h")
    return user.id, device.id


# ---------------------------------------------------------------------------
# prompt_removal unit tests
# ---------------------------------------------------------------------------

def test_prompt_removal_returns_reason() -> None:
    inp = io.StringIO("switching to ag\n")
    out = io.StringIO()
    result = prompt_removal(command="brew uninstall ripgrep", cwd="/tmp", input=inp, output=out)
    assert result.why == "switching to ag"
    assert result.metadata_complete is True


def test_prompt_removal_skip_with_s() -> None:
    inp = io.StringIO("s\n")
    out = io.StringIO()
    result = prompt_removal(command="brew uninstall ripgrep", cwd="/tmp", input=inp, output=out)
    assert result.why is None
    assert result.metadata_complete is False


def test_prompt_removal_skip_with_enter() -> None:
    inp = io.StringIO("\n")
    out = io.StringIO()
    result = prompt_removal(command="brew uninstall ripgrep", cwd="/tmp", input=inp, output=out)
    assert result.why is None
    assert result.metadata_complete is False


def test_prompt_removal_eof_treated_as_skip() -> None:
    inp = io.StringIO("")  # EOF immediately
    out = io.StringIO()
    result = prompt_removal(command="brew uninstall ripgrep", cwd="/tmp", input=inp, output=out)
    assert result.why is None
    assert result.metadata_complete is False


# ---------------------------------------------------------------------------
# capture_removal integration tests
# ---------------------------------------------------------------------------

def _make_install(db: Path, **overrides: object) -> store.Install:
    uid, did = _user_device(db)
    payload: dict[str, object] = dict(
        command="brew install ripgrep",
        package_name="ripgrep",
        manager="brew",
        install_dir="/tmp",
        resolved_path=None,
        exit_code=0,
        user_id=uid,
        device_id=did,
    )
    payload.update(overrides)
    return store.create_install(db, **payload)


def _run_capture_removal(
    db: Path,
    command: str = "brew uninstall ripgrep",
    user_input: str = "no longer needed\n",
) -> store.Install | None:
    from rich.console import Console
    inp = io.StringIO(user_input)
    out = io.StringIO()
    return capture_removal(
        db,
        command_str=command,
        work_dir="/tmp",
        removed_at="2026-05-01T12:00:00+00:00",
        console=Console(file=out),
        input=inp,
        output=out,
    )


def test_capture_removal_updates_existing_row(tmp_path: Path) -> None:
    db = _db(tmp_path)
    inst = _make_install(db)
    result = _run_capture_removal(db)
    assert result is not None
    assert result.id == inst.id
    assert result.removed_at == "2026-05-01T12:00:00+00:00"
    assert result.why == "no longer needed"
    assert result.metadata_complete == 1


def test_capture_removal_creates_new_row_when_no_prior_install(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _user_device(db)  # ensure user/device exist
    result = _run_capture_removal(db)
    assert result is not None
    assert result.removed_at == "2026-05-01T12:00:00+00:00"
    assert result.disposition is None  # purpose unknown


def test_capture_removal_skip_leaves_incomplete(tmp_path: Path) -> None:
    db = _db(tmp_path)
    inst = _make_install(db)
    result = _run_capture_removal(db, user_input="\n")  # skip
    assert result is not None
    assert result.id == inst.id
    assert result.removed_at == "2026-05-01T12:00:00+00:00"
    assert result.metadata_complete == 0


def test_capture_removal_unrecognised_command_returns_none(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _user_device(db)
    from rich.console import Console
    result = capture_removal(
        db,
        command_str="rm -rf node_modules",
        work_dir="/tmp",
        removed_at="2026-05-01T12:00:00+00:00",
        console=Console(file=io.StringIO()),
        input=io.StringIO(""),
        output=io.StringIO(),
    )
    assert result is None
