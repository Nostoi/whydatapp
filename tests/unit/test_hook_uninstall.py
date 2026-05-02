"""Tests for hook_runner dispatch to capture_removal on uninstall commands."""
from __future__ import annotations

from pathlib import Path

import pytest

from why import store
from why.bootstrap import ensure_ready
from why.hook_runner import run_hook


@pytest.fixture(autouse=True)
def _force_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the hook think it's running in an interactive TTY."""
    monkeypatch.setenv("WHY_HOOK_FORCE_PROMPT", "1")


def _seed_install(db: Path, package: str = "ripgrep") -> store.Install:
    user = store.get_solo_user(db)
    device = store.get_solo_device(db)
    assert user and device
    return store.create_install(
        db,
        user_id=user.id,
        device_id=device.id,
        command=f"brew install {package}",
        package_name=package,
        manager="brew",
        install_dir="/tmp",
        resolved_path=None,
        exit_code=0,
    )


def test_hook_dispatches_to_removal_on_uninstall(
    why_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_hook on an uninstall command should mark the existing row removed."""
    db = ensure_ready()
    inst = _seed_install(db)

    # Provide a skip response so prompt doesn't hang.
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO("s\n"))

    run_hook(command="brew uninstall ripgrep", cwd="/tmp", exit_code=0)

    updated = store.get_install(db, inst.id)
    assert updated is not None
    assert updated.removed_at is not None


def test_hook_creates_removal_row_when_no_prior_install(
    why_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_hook on an uninstall for an unknown package should create a new removal row."""
    db = ensure_ready()

    import io
    monkeypatch.setattr("sys.stdin", io.StringIO("s\n"))

    before = store.list_installs(db, store.InstallFilters(show_removed=True))
    run_hook(command="brew uninstall unknown-pkg", cwd="/tmp", exit_code=0)
    after = store.list_installs(db, store.InstallFilters(show_removed=True))

    assert len(after) == len(before) + 1
    new_row = next(r for r in after if r not in before)
    assert new_row.removed_at is not None
    assert new_row.disposition is None


def test_hook_ignores_uninstall_on_nonzero_exit(
    why_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = ensure_ready()
    _seed_install(db)

    import io
    monkeypatch.setattr("sys.stdin", io.StringIO("s\n"))

    run_hook(command="brew uninstall ripgrep", cwd="/tmp", exit_code=1)

    inst = store.find_existing_install(db, manager="brew", package_name="ripgrep")
    assert inst is not None
    assert inst.removed_at is None


def test_hook_still_captures_installs(
    why_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure normal install path still works after the dispatch refactor."""
    db = ensure_ready()

    import io
    monkeypatch.setattr("sys.stdin", io.StringIO("s\n"))

    run_hook(command="brew install jq", cwd="/tmp", exit_code=0)

    rows = store.list_installs(db, store.InstallFilters())
    assert any(r.package_name == "jq" for r in rows)
