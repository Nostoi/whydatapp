"""Drive the real shell hooks through an actual prompt cycle.

These tests shim `why` with a logging stub so they exercise the *hook's control
flow* rather than the CLI's contract. tests/integration/test_hook_shell.py covers
the latter, but hand-writes its own `why _hook` invocation and therefore cannot
catch a hook that never reaches it.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[2] / "src" / "why" / "shells"


def _make_shim(tmp_path: Path, *, follow_status: str = "inactive") -> tuple[Path, Path]:
    """A fake `why` on PATH that logs argv and answers `follow status`."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    calls = tmp_path / "calls.log"
    shim = bin_dir / "why"
    shim.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$*" >> "{calls}"\n'
        'if [ "$1" = "follow" ] && [ "$2" = "status" ]; then\n'
        f"  printf '{follow_status}'\n"
        "fi\n"
        "exit 0\n"
    )
    shim.chmod(0o755)
    return bin_dir, calls


def _run_zsh(script: str, tmp_path: Path, bin_dir: Path) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "home"
    (home / ".why").mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        ["zsh", "-f", "-c", script],
        capture_output=True,
        text=True,
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "HOME": str(home),
            "ZDOTDIR": str(home),
        },
    )


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh not available")
def test_precmd_invokes_record_in_zsh(tmp_path: Path):
    """A full preexec+precmd cycle must reach `why _record`.

    Regression test: `local status` in _why_update_prompt aborted the function
    (zsh's $status is read-only), which silently killed _record AND _hook.
    """
    bin_dir, calls = _make_shim(tmp_path)
    result = _run_zsh(
        f"source {HOOKS}/hook.zsh\n"
        "_why_preexec 'echo hello'\n"
        "_why_precmd\n",
        tmp_path,
        bin_dir,
    )

    logged = calls.read_text() if calls.exists() else ""
    assert "_record" in logged, (
        f"_why_precmd never reached `why _record`.\nstderr: {result.stderr}\ncalls: {logged!r}"
    )
    assert "--cmd echo hello" in logged


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh not available")
def test_precmd_emits_no_stderr_in_zsh(tmp_path: Path):
    """The hook must never print to the user's terminal on a normal prompt draw.

    pytest has no controlling terminal, so the `_hook` line's `</dev/tty` redirect
    reports "device not configured". That cannot happen in a real interactive shell,
    which is the only context precmd runs in, so it is filtered out here. Every other
    line of stderr is a genuine defect (this test failed on `read-only variable: status`).
    """
    bin_dir, _ = _make_shim(tmp_path)
    result = _run_zsh(
        f"source {HOOKS}/hook.zsh\n_why_preexec 'echo hello'\n_why_precmd\n",
        tmp_path,
        bin_dir,
    )

    noise = [ln for ln in result.stderr.splitlines() if ln.strip() and "/dev/tty" not in ln]
    assert noise == [], f"hook wrote to stderr: {noise!r}"


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh not available")
def test_dynamic_prompt_still_updates_when_inactive(tmp_path: Path):
    """A theme that recomputes PROMPT each prompt must not be frozen by the hook.

    Regression test: WHY_ORIGINAL_PROMPT was a load-time snapshot that the
    else-branch restored unconditionally, freezing starship/p10k-style prompts
    for every zsh user whether or not they used `why follow`.
    """
    bin_dir, _ = _make_shim(tmp_path, follow_status="inactive")
    result = _run_zsh(
        f"PROMPT='first> '\n"
        f"source {HOOKS}/hook.zsh\n"
        "PROMPT='second> '\n"  # the theme recomputes the prompt
        "_why_precmd\n"
        'printf "FINAL:%s\\n" "$PROMPT"\n',
        tmp_path,
        bin_dir,
    )

    assert "FINAL:second> " in result.stdout, (
        f"hook clobbered a dynamic prompt.\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


def _run_bash(script: str, tmp_path: Path, bin_dir: Path) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "home"
    (home / ".why").mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        ["bash", "--norc", "--noprofile", "-c", script],
        capture_output=True,
        text=True,
        env={"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(home)},
    )


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_dynamic_ps1_still_updates_when_inactive_in_bash(tmp_path: Path):
    """bash carries the same load-time PS1 snapshot bug as zsh."""
    bin_dir, _ = _make_shim(tmp_path, follow_status="inactive")
    result = _run_bash(
        f"PS1='first> '\n"
        f"source {HOOKS}/hook.bash\n"
        "PS1='second> '\n"
        "_why_update_prompt_bash\n"
        'printf "FINAL:%s\\n" "$PS1"\n',
        tmp_path,
        bin_dir,
    )

    assert "FINAL:second> " in result.stdout, (
        f"hook clobbered a dynamic PS1.\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_indicator_survives_user_prompt_command_in_bash(tmp_path: Path):
    """A user PROMPT_COMMAND that rewrites PS1 must not defeat the indicator.

    Regression test: _why_precmd_bash was *prepended* to PROMPT_COMMAND, so a
    user entry running afterwards won the PS1 race and the indicator never showed.
    """
    bin_dir, _ = _make_shim(tmp_path, follow_status="active")
    result = _run_bash(
        "PS1='base> '\n"
        "PROMPT_COMMAND=\"PS1='theme> '\"\n"  # a theme that rewrites PS1 each prompt
        f"source {HOOKS}/hook.bash\n"
        'eval "$PROMPT_COMMAND"\n'
        'printf "FINAL:%s\\n" "$PS1"\n',
        tmp_path,
        bin_dir,
    )

    assert "FINAL:[why rec] theme> " in result.stdout, (
        f"user PROMPT_COMMAND defeated the indicator.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh not available")
def test_active_session_prefixes_current_prompt_in_zsh(tmp_path: Path):
    """The [why rec] indicator applies to the *current* prompt, not a stale snapshot."""
    bin_dir, _ = _make_shim(tmp_path, follow_status="active")
    result = _run_zsh(
        f"PROMPT='first> '\n"
        f"source {HOOKS}/hook.zsh\n"
        "PROMPT='second> '\n"
        "_why_precmd\n"
        'printf "FINAL:%s\\n" "$PROMPT"\n',
        tmp_path,
        bin_dir,
    )

    assert "FINAL:[why rec] second> " in result.stdout, (
        f"indicator used a stale prompt.\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh not available")
def test_missing_why_home_does_not_write_to_terminal(tmp_path: Path):
    """A missing ~/.why must not leak redirect errors onto the user's terminal.

    Regression test: `2>>"$HOME/.why/hook.log"` is evaluated by the shell *before*
    the command runs, so when the directory is absent the error goes to the TTY and
    `|| true` cannot suppress it -- and _record never executes at all.
    """
    bin_dir, calls = _make_shim(tmp_path)
    home = tmp_path / "nohome"
    home.mkdir()  # deliberately WITHOUT .why
    result = subprocess.run(
        ["zsh", "-f", "-c", f"source {HOOKS}/hook.zsh\n_why_preexec 'echo hi'\n_why_precmd\n"],
        capture_output=True,
        text=True,
        env={"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(home), "ZDOTDIR": str(home)},
    )

    noise = [ln for ln in result.stderr.splitlines() if ln.strip() and "/dev/tty" not in ln]
    assert noise == [], f"hook leaked to terminal with no ~/.why: {noise!r}"
    assert "_record" in (calls.read_text() if calls.exists() else ""), "_record never ran"


# --- fish ------------------------------------------------------------------
#
# These skip when fish is absent. They exist so the fish hook stops depending on a
# manual pass: install fish and the suite covers it. See docs/guide/development.md.


def _run_fish(script: str, tmp_path: Path, bin_dir: Path) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "fishhome"
    (home / ".why").mkdir(parents=True, exist_ok=True)
    # Resolve fish absolutely: PATH is deliberately restricted below so the shim is
    # the only `why`, and Homebrew's fish lives outside /usr/bin:/bin.
    fish = shutil.which("fish") or "fish"
    return subprocess.run(
        [fish, "--no-config", "-c", script],
        capture_output=True,
        text=True,
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
        },
    )


@pytest.mark.skipif(shutil.which("fish") is None, reason="fish not available")
def test_fish_prompt_emits_no_stderr(tmp_path: Path):
    """`status` is read-only in fish, as in zsh.

    Regression test: `set -l status (...)` in the wrapped fish_prompt printed
    "set: Tried to change the read-only variable 'status'" on EVERY prompt draw and
    left the [why rec] indicator permanently off, because $status then read the
    failed set's own exit code.
    """
    bin_dir, _ = _make_shim(tmp_path)
    result = _run_fish(
        "function fish_prompt; printf 'base> '; end\n"
        f"source {HOOKS}/hook.fish\n"
        "fish_prompt\n",
        tmp_path,
        bin_dir,
    )

    assert "read-only" not in result.stderr, f"fish hook errored: {result.stderr!r}"
    assert result.stderr.strip() == "", f"fish hook wrote to stderr: {result.stderr!r}"


@pytest.mark.skipif(shutil.which("fish") is None, reason="fish not available")
def test_fish_prompt_shows_indicator_when_active(tmp_path: Path):
    bin_dir, _ = _make_shim(tmp_path, follow_status="active")
    result = _run_fish(
        "function fish_prompt; printf 'base> '; end\n"
        f"source {HOOKS}/hook.fish\n"
        "fish_prompt\n",
        tmp_path,
        bin_dir,
    )

    assert "[why rec] base> " in result.stdout, (
        f"indicator missing.\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


@pytest.mark.skipif(shutil.which("fish") is None, reason="fish not available")
def test_fish_prompt_hides_indicator_when_inactive(tmp_path: Path):
    bin_dir, _ = _make_shim(tmp_path, follow_status="inactive")
    result = _run_fish(
        "function fish_prompt; printf 'base> '; end\n"
        f"source {HOOKS}/hook.fish\n"
        "fish_prompt\n",
        tmp_path,
        bin_dir,
    )

    assert "[why rec]" not in result.stdout
    assert "base> " in result.stdout


@pytest.mark.skipif(shutil.which("fish") is None, reason="fish not available")
def test_fish_postexec_invokes_record(tmp_path: Path):
    """A completed command must reach `why _record` in fish too."""
    bin_dir, calls = _make_shim(tmp_path)
    result = _run_fish(
        f"source {HOOKS}/hook.fish\n"
        "set -g WHY_LAST_CMD 'echo hello'\n"
        "set -g WHY_LAST_PWD /tmp\n"
        "_why_postexec\n",
        tmp_path,
        bin_dir,
    )

    logged = calls.read_text() if calls.exists() else ""
    assert "_record" in logged, (
        f"_why_postexec never reached `why _record`.\nstderr: {result.stderr}\ncalls: {logged!r}"
    )
