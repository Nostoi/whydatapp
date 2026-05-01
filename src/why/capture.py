"""Shared capture logic for the shell hook and `why log`.

Both paths converge here so that enrichment, prefill, and new-entry flows
live in exactly one place.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import IO

from rich.console import Console

from why import store
from why.detect import match_install
from why.humanize import time_ago
from why.project_infer import infer_project
from why.prompts import run_metadata_prompt
from why.resolve import resolve_path


def capture(
    db: Path,
    *,
    command_str: str,
    work_dir: str,
    enrich: bool,
    console: Console,
    input: IO[str],
    output: IO[str],
) -> store.Install | None:
    """Run the full capture flow for a single install command.

    Returns the Install row that was created or updated, or None when the
    command was skipped / not recognised / was a silent re-install.
    """
    match = match_install(command_str)
    if match is None:
        console.print(
            f"[yellow]not recognized as an install: {command_str}[/yellow]"
        )
        return None

    if store.recent_duplicate_exists(
        db, command=command_str, install_dir=work_dir, within_seconds=60
    ):
        console.print("[dim]recent duplicate; skipping.[/dim]")
        return None

    user = store.get_solo_user(db)
    device = store.get_solo_device(db)
    assert user is not None and device is not None

    primary_pkg = match.packages[0]
    resolved = resolve_path(manager=match.manager, package=primary_pkg, cwd=work_dir)

    # --- Enrichment branch (hook path or explicit --enrich flag) ---
    if enrich and primary_pkg:
        existing = store.find_existing_install(
            db, manager=match.manager, package_name=primary_pkg
        )

        if existing is not None and existing.metadata_complete == 1:
            # Complete record — silent re-install enrichment.
            updated = store.record_reinstall(db, existing.id)
            prev_ts = existing.last_installed_at or existing.installed_at
            ago = time_ago(prev_ts)
            display = updated.display_name or primary_pkg
            sys.stdout.write(
                f"↻ {display} re-installed (id={updated.id}, last seen {ago})\n"
            )
            sys.stdout.flush()
            return None  # silent path — no new install row

        if existing is not None and existing.metadata_complete == 0:
            # Incomplete record — surface prompt with prefill, then update the same row.
            inferred_project = existing.project or infer_project(work_dir)
            result = run_metadata_prompt(
                default_name=existing.display_name or primary_pkg,
                default_project=inferred_project,
                command=command_str,
                cwd=work_dir,
                input=input,
                output=output,
            )

            if result.disposition == "skip":
                console.print(
                    f"  [dim]skipped — review later via `why review` (id={existing.id})[/dim]"
                )
                return None

            if result.project:
                store.upsert_project(db, result.project)

            store.update_install(
                db,
                existing.id,
                display_name=result.display_name,
                what_it_does=result.what_it_does,
                project=result.project,
                why=result.why,
                notes=result.notes,
                disposition=result.disposition,
                metadata_complete=1 if result.metadata_complete else 0,
            )
            console.print(f"  [green]✓[/green] updated (id={existing.id}).")
            return store.get_install(db, existing.id)

    # --- No existing match, or enrich=False — create a new entry ---
    inst = store.create_install(
        db,
        user_id=user.id,
        device_id=device.id,
        command=command_str,
        package_name=primary_pkg,
        manager=match.manager,
        install_dir=work_dir,
        resolved_path=resolved,
        exit_code=0,
    )

    inferred_project = infer_project(work_dir)
    result = run_metadata_prompt(
        default_name=primary_pkg,
        default_project=inferred_project,
        command=command_str,
        cwd=work_dir,
        input=input,
        output=output,
    )

    if result.disposition == "skip":
        console.print(
            f"  [dim]skipped — review later via `why review` (id={inst.id})[/dim]"
        )
        return inst  # row exists but incomplete — still return it for history

    if result.project:
        store.upsert_project(db, result.project)

    store.update_install(
        db,
        inst.id,
        display_name=result.display_name,
        what_it_does=result.what_it_does,
        project=result.project,
        why=result.why,
        notes=result.notes,
        disposition=result.disposition,
        metadata_complete=1 if result.metadata_complete else 0,
    )
    console.print(f"  [green]✓[/green] logged (id={inst.id}).")
    return inst
