from __future__ import annotations

import io

from why.prompts import run_metadata_prompt


def test_run_metadata_prompt_skip_path():
    inp = io.StringIO("s\n")
    out = io.StringIO()
    res = run_metadata_prompt(
        default_name="ripgrep",
        default_project="whydatapp",
        command="brew install ripgrep",
        cwd="/tmp",
        input=inp,
        output=out,
    )
    assert res.disposition == "skip"
    assert res.metadata_complete is False


def test_run_metadata_prompt_full_path():
    # "1" → first built-in purpose = doc/Reference
    answers = "\n".join([
        "1",
        "ripgrep",
        "fast grep",
        "whydatapp",
        "needed for code search",
        "",
    ]) + "\n"
    res = run_metadata_prompt(
        default_name="ripgrep",
        default_project="whydatapp",
        command="brew install ripgrep",
        cwd="/tmp",
        input=io.StringIO(answers),
        output=io.StringIO(),
    )
    # First purpose from fallback defaults is "doc"
    assert res.disposition == "doc"
    assert res.display_name == "ripgrep"
    assert res.what_it_does == "fast grep"
    assert res.project == "whydatapp"
    assert res.why == "needed for code search"
    assert res.notes is None
    assert res.metadata_complete is True


def test_run_metadata_prompt_quit_marks_ignore():
    res = run_metadata_prompt(
        default_name="x", default_project=None,
        command="brew install x", cwd="/tmp",
        input=io.StringIO("q\n"),
        output=io.StringIO(),
    )
    assert res.disposition == "ignore"
    assert res.metadata_complete is True


def test_run_metadata_prompt_invalid_then_valid():
    answers = "x\nz\n2\nname\nwhat\nproj\nwhy\n\n"
    res = run_metadata_prompt(
        default_name=None, default_project=None,
        command="brew install y", cwd="/tmp",
        input=io.StringIO(answers),
        output=io.StringIO(),
    )
    # "2" → second built-in purpose = "setup"
    assert res.disposition == "setup"
    assert res.metadata_complete is True
