"""Stale shell-hook detection and auto-refresh.

The hooks have always *declared* WHY_HOOK_VERSION; until 2.3.0 nothing read it,
so a hook bugfix only reached a user who independently re-ran `why init`.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from why.shells import installer
from why.shells.installer import (
    SHELLS,
    installed_hook_version,
    packaged_hook_version,
    refresh_stale_hooks,
)


def test_every_packaged_hook_declares_a_version():
    """A hook that loses its marker would silently opt out of auto-refresh forever."""
    versions = {shell: packaged_hook_version(shell) for shell in SHELLS}
    assert all(isinstance(v, int) for v in versions.values())
    assert len(set(versions.values())) == 1, f"hook versions drifted: {versions}"


def test_packaged_hook_version_rejects_unknown_shell():
    with pytest.raises(ValueError):
        packaged_hook_version("nushell")


@pytest.mark.parametrize(
    ("shell", "text", "expected"),
    [
        ("zsh", "# c\nWHY_HOOK_VERSION=7\n", 7),
        ("bash", "WHY_HOOK_VERSION=12\n", 12),
        ("fish", "set -g WHY_HOOK_VERSION 3\n", 3),
        ("zsh", "no marker here\n", None),
        ("zsh", "WHY_HOOK_VERSION=abc\n", None),
    ],
)
def test_installed_hook_version_parsing(
    why_home: Path, shell: str, text: str, expected: int | None
):
    (why_home / f"hook.{shell}").write_text(text)
    assert installed_hook_version(shell, why_home) == expected


def test_installed_hook_version_is_none_when_file_absent(why_home: Path):
    assert installed_hook_version("zsh", why_home) is None


def test_refresh_rewrites_a_stale_hook(why_home: Path):
    target = why_home / "hook.zsh"
    target.write_text("WHY_HOOK_VERSION=1\n_why_precmd() { :; }\n")

    refreshed = refresh_stale_hooks(why_home)

    assert refreshed == [("zsh", 1, packaged_hook_version("zsh"))]
    assert target.read_text() == installer.packaged_hook_text("zsh")


def test_refresh_rewrites_a_hook_with_no_version_marker(why_home: Path):
    """A pre-versioning hook must still be upgradeable; old version reads as None."""
    target = why_home / "hook.bash"
    target.write_text("# ancient hook, no marker\n")

    refreshed = refresh_stale_hooks(why_home)

    assert refreshed == [("bash", None, packaged_hook_version("bash"))]
    assert "WHY_HOOK_VERSION" in target.read_text()


def test_refresh_is_a_noop_when_up_to_date(why_home: Path):
    target = why_home / "hook.fish"
    target.write_text(installer.packaged_hook_text("fish"))
    before = target.stat().st_mtime_ns

    assert refresh_stale_hooks(why_home) == []
    assert target.stat().st_mtime_ns == before


def test_refresh_never_creates_a_hook_that_was_not_installed(why_home: Path):
    """`why uninstall` leaves ~/.why in place; we must not resurrect hook files."""
    assert refresh_stale_hooks(why_home) == []
    assert list(why_home.iterdir()) == []


def test_refresh_covers_every_installed_shell(why_home: Path):
    for shell in SHELLS:
        (why_home / f"hook.{shell}").write_text("WHY_HOOK_VERSION=1\n")

    refreshed = refresh_stale_hooks(why_home)

    assert {shell for shell, _, _ in refreshed} == set(SHELLS)


def test_refresh_never_downgrades_a_newer_hook(why_home: Path):
    """Running an older `why` alongside a newer one must not thrash the file."""
    target = why_home / "hook.zsh"
    text = f"WHY_HOOK_VERSION={packaged_hook_version('zsh') + 1}\n"
    target.write_text(text)

    assert refresh_stale_hooks(why_home) == []
    assert target.read_text() == text


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
def test_refresh_is_silent_when_the_hook_is_unwritable(why_home: Path):
    """A read-only ~/.why must degrade, not raise: hook.log is unwritable too."""
    target = why_home / "hook.zsh"
    target.write_text("WHY_HOOK_VERSION=1\n")
    target.chmod(0o400)
    try:
        assert refresh_stale_hooks(why_home) == []
        assert target.read_text() == "WHY_HOOK_VERSION=1\n"
    finally:
        target.chmod(0o600)
