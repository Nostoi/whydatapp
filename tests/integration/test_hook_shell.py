from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh not available")
def test_hook_captures_real_install(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    why = home / ".why"
    monkeypatch.setenv("WHY_HOME", str(why))

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    brew = bin_dir / "brew"
    brew.write_text("#!/bin/sh\nexit 0\n")
    brew.chmod(0o755)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SHELL", "/bin/zsh")
    init_answers = "\n".join(["lab"] + ["y"] * 11 + ["n", "", "n", "y"]) + "\n"
    subprocess.run(
        ["uv", "run", "why", "init"],
        input=init_answers,
        text=True,
        check=True,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
    )

    script = f"""
    set -e
    source {why}/hook.zsh
    WHY_LAST_CMD='brew install ripgrep'
    WHY_LAST_PWD={tmp_path}
    WHY_SUPPRESS=1 why _hook --cmd "$WHY_LAST_CMD" --cwd "$WHY_LAST_PWD" \
        --code 0 < /dev/null > /dev/null 2>&1 || true
    """
    subprocess.run(
        ["zsh", "-i", "-c", script],
        check=True,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "HOME": str(home),
            "WHY_HOME": str(why),
        },
    )

    assert (why / "data.db").exists()
