from __future__ import annotations

from dataclasses import dataclass
from typing import IO

from rich.console import Console
from rich.rule import Rule
from rich.style import Style

_TEAL = Style(color="cyan", bold=True)


def _print_banner(output: IO[str], verb: str) -> None:
    """Print a teal rule line: ─── whydatApp <verb>? ──────────"""
    console = Console(file=output, highlight=False, markup=False)
    console.print(Rule(f"whydatApp {verb}?", style=_TEAL, align="left"))


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


def _load_purposes() -> list[tuple[str, str]]:
    """Return [(key, label), ...] from DB, or built-in defaults on any error."""
    try:
        from why import store
        from why.bootstrap import ensure_ready
        db = ensure_ready()
        return [(p.key, p.label) for p in store.list_purposes(db)]
    except Exception:
        return [
            ("doc", "Reference"),
            ("setup", "Project setup"),
            ("experimental", "Trying out"),
            ("remove", "Cleanup soon"),
            ("ignore", "Ignore"),
        ]


def run_metadata_prompt(
    *,
    default_name: str | None,
    default_project: str | None,
    command: str,
    cwd: str,
    input: IO[str],
    output: IO[str],
) -> PromptResult:
    purposes = _load_purposes()

    # Build numeric mapping 1..N → (key, label)
    numeric_map: dict[str, str] = {}  # digit → key
    parts = []
    for i, (key, label) in enumerate(purposes, start=1):
        numeric_map[str(i)] = key
        parts.append(f"[{i}] {label}")

    output.write("\n")
    _print_banner(output, "installed")
    output.write(f"  {command}  ({cwd})\n\n")
    output.write("  Purpose? " + "  ".join(parts) + "\n")
    output.write("  [s] Skip for now    [q] Quit (treat as ignore)\n")
    output.flush()

    chosen_key: str | None = None
    is_skip = False
    is_quit = False

    while True:
        output.write("> ")
        output.flush()
        line = input.readline()
        if not line:
            return PromptResult("skip", None, None, None, None, None, False)
        val = line.strip().lower()
        if val == "s":
            is_skip = True
            break
        if val == "q":
            is_quit = True
            break
        if val in numeric_map:
            chosen_key = numeric_map[val]
            break
        output.write("  invalid choice; try again.\n")

    if is_skip:
        return PromptResult("skip", None, None, None, None, None, False)
    if is_quit:
        return PromptResult("ignore", None, None, None, None, None, True)

    name = _ask("Display name", default=default_name or "", input=input, output=output) or None
    what = _ask("What does it do?", default=None, input=input, output=output) or None
    project = _ask("Project", default=default_project or "", input=input, output=output) or None
    why = _ask("Why install?", default=None, input=input, output=output) or None
    notes = _ask("Notes (optional, ↵ to skip)", default=None, input=input, output=output) or None

    return PromptResult(
        disposition=chosen_key or "ignore",
        display_name=name,
        what_it_does=what,
        project=project,
        why=why,
        notes=notes,
        metadata_complete=True,
    )


@dataclass(frozen=True)
class RemovalPromptResult:
    why: str | None          # reason for removal; None means skipped
    metadata_complete: bool  # True when user provided a reason


def prompt_removal(
    *,
    command: str,
    cwd: str,
    input: IO[str],
    output: IO[str],
) -> RemovalPromptResult:
    """Prompt the user for why they removed a package.

    A single optional question — skip with ↵ or [s].  Ctrl-C / EOF treated as
    skip (same mechanic as run_metadata_prompt).
    """
    output.write("\n")
    _print_banner(output, "deleted")
    output.write(f"  {command}  ({cwd})\n\n")
    output.write("  Why did you remove it? (↵ or [s] to skip)\n")
    output.flush()

    try:
        output.write("> ")
        output.flush()
        line = input.readline()
    except (KeyboardInterrupt, EOFError):
        output.write("\n")
        return RemovalPromptResult(why=None, metadata_complete=False)

    if not line:
        return RemovalPromptResult(why=None, metadata_complete=False)

    val = line.rstrip("\n").strip()
    if val.lower() == "s" or val == "":
        return RemovalPromptResult(why=None, metadata_complete=False)

    return RemovalPromptResult(why=val, metadata_complete=True)

