import sys
from pathlib import Path

import pytest

from why.autostart import (
    install_linux_systemd,
    install_macos_launchd,
    uninstall_linux_systemd,
    uninstall_macos_launchd,
)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-only")
def test_macos_writes_plist(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    plist = install_macos_launchd(why_path="/usr/local/bin/why", port=7873, dry_run=True)
    assert "<key>Label</key>" in plist
    assert "/usr/local/bin/why" in plist
    assert "<string>serve</string>" in plist


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux-only")
def test_linux_writes_unit(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    unit = install_linux_systemd(why_path="/usr/local/bin/why", port=7873, dry_run=True)
    assert "ExecStart=/usr/local/bin/why serve --no-open" in unit
    assert "Restart=on-failure" in unit


def test_uninstall_no_op_when_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    if sys.platform == "darwin":
        uninstall_macos_launchd()
    elif sys.platform.startswith("linux"):
        uninstall_linux_systemd()
