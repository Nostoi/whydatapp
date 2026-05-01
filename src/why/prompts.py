from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import IO


class DispositionChoice(Enum):
    DOC = "doc"
    SETUP = "setup"
    EXPERIMENTAL = "experimental"
    REMOVE = "remove"
    IGNORE = "ignore"
    SKIP = "skip"
    QUIT = "quit"


_NUMERIC = {
    "1": DispositionChoice.DOC,
    "2": DispositionChoice.SETUP,
    "3": DispositionChoice.EXPERIMENTAL,
    "4": DispositionChoice.REMOVE,
    "5": DispositionChoice.IGNORE,
    "s": DispositionChoice.SKIP,
    "q": DispositionChoice.QUIT,
}


def parse_disposition_input(s: str) -> DispositionChoice | None:
    return _NUMERIC.get(s.strip().lower())


@dataclass(frozen=True)
class PromptResult:
    disposition: str
    display_name: str | None
    what_it_does: str | None
    project: str | None
    why: str | None
    notes: str | None
    metadata_complete: bool


def _ask(prompt: str, *, input: IO[str], output: IO[str], default: str | None = None) -> str:
    if default:
        output.write(f"  {prompt} [{default}]: ")
    else:
        output.write(f"  {prompt}: ")
    output.flush()
    line = input.readline()
    if not line:
        return ""
    val = line.rstrip("\n")
    return val if val else (default or "")


def run_metadata_prompt(
    *,
    default_name: str | None,
    default_project: str | None,
    command: str,
    cwd: str,
    input: IO[str],
    output: IO[str],
) -> PromptResult:
    output.write(f"\n📝 why? — captured: {command}  ({cwd})\n\n")
    output.write("  Purpose? [1] Reference  [2] Project setup  [3] Trying out  "
                 "[4] Cleanup soon  [5] Ignore\n")
    output.write("  [s] Skip for now    [q] Quit (treat as ignore)\n")
    output.flush()

    while True:
        output.write("> ")
        output.flush()
        line = input.readline()
        if not line:
            return PromptResult("skip", None, None, None, None, None, False)
        choice = parse_disposition_input(line)
        if choice is not None:
            break
        output.write("  invalid choice; try again.\n")

    if choice == DispositionChoice.SKIP:
        return PromptResult("skip", None, None, None, None, None, False)
    if choice == DispositionChoice.QUIT:
        return PromptResult("ignore", None, None, None, None, None, True)

    name = _ask("Display name", default=default_name or "", input=input, output=output) or None
    what = _ask("What does it do?", default=None, input=input, output=output) or None
    project = _ask("Project", default=default_project or "", input=input, output=output) or None
    why = _ask("Why install?", default=None, input=input, output=output) or None
    notes = _ask("Notes (optional, ↵ to skip)", default=None, input=input, output=output) or None

    return PromptResult(
        disposition=choice.value,
        display_name=name,
        what_it_does=what,
        project=project,
        why=why,
        notes=notes,
        metadata_complete=True,
    )
