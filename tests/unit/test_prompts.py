from __future__ import annotations

import io

from why.prompts import (
    DispositionChoice,
    parse_disposition_input,
    run_metadata_prompt,
)


def test_parse_disposition_input_numeric():
    assert parse_disposition_input("1") == DispositionChoice.DOC
    assert parse_disposition_input("2") == DispositionChoice.SETUP
    assert parse_disposition_input("3") == DispositionChoice.EXPERIMENTAL
    assert parse_disposition_input("4") == DispositionChoice.REMOVE
    assert parse_disposition_input("5") == DispositionChoice.IGNORE


def test_parse_disposition_input_skip_and_quit():
    assert parse_disposition_input("s") == DispositionChoice.SKIP
    assert parse_disposition_input("q") == DispositionChoice.QUIT


def test_parse_disposition_input_invalid():
    assert parse_disposition_input("x") is None
    assert parse_disposition_input("") is None


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
