from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from why import store
from why.config import load_config, load_llm_ignore_patterns, write_config
from why.llm import (
    PROMPT_VERSION,
    SYSTEM_PROMPT_V1,
    build_task_payload,
    build_user_prompt,
    normalized_payload_hash,
    requires_confirmation,
    summarize_openai_compatible,
)
from why.paths import log_error
from why.web.deps import get_db, get_presentation
from why.web.templates_env import make_env

router = APIRouter()
_env = make_env()


def _ctx(db: Path, pres: dict[str, Any]) -> dict[str, Any]:
    return {
        "pres": pres,
        "review_count": len(store.list_skipped(db)),
        "q": "",
    }


def _session_rows(db: Path, summary_status: str | None) -> list[dict[str, object]]:
    sessions = store.list_task_sessions(db, summary_status=summary_status, limit=200)
    rows: list[dict[str, object]] = []
    for session in sessions:
        latest_summary = next(iter(store.list_task_session_summaries(db, session.id)), None)
        rows.append(
            {
                "session": session,
                "command_count": len(store.list_task_session_commands(db, session.id)),
                "latest_summary": latest_summary,
            }
        )
    return rows


@router.get("/sessions", response_class=HTMLResponse)
def sessions_page(
    request: Request,
    summary_status: str | None = None,
    db: Path = Depends(get_db),  # noqa: B008
    pres: dict[str, Any] = Depends(get_presentation),  # noqa: B008
) -> HTMLResponse:
    ctx = _ctx(db, pres)
    ctx.update(
        {
            "rows": _session_rows(db, summary_status),
            "summary_status": summary_status or "",
        }
    )
    return HTMLResponse(_env.get_template("sessions.html").render(request=request, **ctx))


@router.get("/sessions/{session_id}", response_class=HTMLResponse)
def session_detail(
    request: Request,
    session_id: int,
    confirm: int = 0,
    db: Path = Depends(get_db),  # noqa: B008
    pres: dict[str, Any] = Depends(get_presentation),  # noqa: B008
) -> HTMLResponse:
    session = store.get_task_session(db, session_id)
    if session is None:
        return HTMLResponse("Not found", status_code=404)
    summaries = store.list_task_session_summaries(db, session.id)
    llm_cfg = load_config()["llm"]
    ctx = _ctx(db, pres)
    ctx.update(
        {
            "session": session,
            "commands": store.list_task_session_commands(db, session.id),
            "summaries": summaries,
            "latest_summary": summaries[0] if summaries else None,
            "confirm_send": bool(confirm),
            "llm_endpoint": str(llm_cfg["base_url"]),
            "llm_model": str(llm_cfg["model"]),
        }
    )
    return HTMLResponse(_env.get_template("session_detail.html").render(request=request, **ctx))


@router.post("/sessions/{session_id}/ignore-llm")
def session_ignore_llm(
    session_id: int,
    db: Path = Depends(get_db),  # noqa: B008
) -> RedirectResponse:
    store.set_task_session_summary_status(db, session_id, "ignored")
    return RedirectResponse(url=f"/sessions/{session_id}", status_code=303)


@router.post("/sessions/{session_id}/unignore-llm")
def session_unignore_llm(
    session_id: int,
    db: Path = Depends(get_db),  # noqa: B008
) -> RedirectResponse:
    store.set_task_session_summary_status(db, session_id, "none")
    return RedirectResponse(url=f"/sessions/{session_id}", status_code=303)


@router.post("/sessions/{session_id}/delete")
def session_delete(
    session_id: int,
    purge: str = Form(""),  # noqa: B008
    db: Path = Depends(get_db),  # noqa: B008
) -> RedirectResponse:
    if purge == "1":
        store.purge_task_session(db, session_id)
    else:
        store.soft_delete_task_session(db, session_id)
    return RedirectResponse(url="/sessions", status_code=303)


def _known_installs_for_commands(
    db: Path, commands: list[store.TaskSessionCommand]
) -> list[store.Install]:
    installs: list[store.Install] = []
    seen: set[int] = set()
    for command in commands:
        if command.matched_install_id is None or command.matched_install_id in seen:
            continue
        inst = store.get_install(db, command.matched_install_id)
        if inst is not None:
            installs.append(inst)
            seen.add(inst.id)
    return installs


@router.post("/sessions/{session_id}/summarize")
def session_summarize(
    session_id: int,
    confirmed: str = Form(""),  # noqa: B008
    db: Path = Depends(get_db),  # noqa: B008
) -> RedirectResponse:
    session = store.get_task_session(db, session_id)
    if session is None:
        return RedirectResponse(url="/sessions", status_code=303)
    cfg = load_config()
    llm_cfg = cfg["llm"]
    if not llm_cfg["enabled"]:
        return RedirectResponse(url=f"/settings/llm?session_id={session_id}", status_code=303)

    # Honour confirm_before_send exactly as the CLI does. Without this the user's
    # transcript would leave the machine on a single click.
    if confirmed != "1" and requires_confirmation(
        str(llm_cfg["confirm_before_send"]), str(llm_cfg["base_url"])
    ):
        return RedirectResponse(url=f"/sessions/{session_id}?confirm=1", status_code=303)

    commands = store.list_task_session_commands(db, session.id)
    try:
        payload = build_task_payload(
            session,
            commands,
            _known_installs_for_commands(db, commands),
            max_commands=int(llm_cfg["max_input_commands"]),
            llm_ignore_patterns=load_llm_ignore_patterns(),
        )
    except ValueError as e:
        # A bad user-authored regex in llm-ignore.toml is a config problem, not a
        # server error. Previously this escaped the route as an HTTP 500.
        log_error(f"summarize config error (session {session_id}): {e}")
        store.set_task_session_summary_status(db, session.id, "failed")
        return RedirectResponse(url=f"/sessions/{session_id}", status_code=303)

    try:
        summary = summarize_openai_compatible(
            base_url=str(llm_cfg["base_url"]),
            api_key=os.environ.get(str(llm_cfg["api_key_env"])),
            model=str(llm_cfg["model"]),
            system_prompt=SYSTEM_PROMPT_V1,
            user_prompt=build_user_prompt(payload),
            timeout_seconds=int(llm_cfg["timeout_seconds"]),
        )
        if llm_cfg["store_summaries"]:
            store.save_task_session_summary(
                db,
                session.id,
                provider=str(llm_cfg["provider"]),
                model=str(llm_cfg["model"]),
                endpoint=str(llm_cfg["base_url"]),
                prompt_version=PROMPT_VERSION,
                input_hash=normalized_payload_hash(payload),
                summary_markdown=summary,
            )
        else:
            # save_task_session_summary is what normally sets 'complete'.
            store.set_task_session_summary_status(db, session.id, "complete")
    except Exception as e:  # noqa: BLE001 - surface, don't swallow
        # A blanket suppress collapsed every distinct failure (bad key, DNS,
        # timeout, malformed response) into one silent "failed" badge.
        log_error(f"summarize failed (session {session_id}): {e}")
        store.set_task_session_summary_status(db, session.id, "failed")
    return RedirectResponse(url=f"/sessions/{session_id}", status_code=303)


@router.get("/settings/llm", response_class=HTMLResponse)
def settings_llm(
    request: Request,
    session_id: int | None = None,
    db: Path = Depends(get_db),  # noqa: B008
    pres: dict[str, Any] = Depends(get_presentation),  # noqa: B008
) -> HTMLResponse:
    ctx = _ctx(db, pres)
    ctx.update({"llm": load_config()["llm"], "session_id": session_id})
    return HTMLResponse(_env.get_template("settings_llm.html").render(request=request, **ctx))


@router.post("/settings/llm")
def settings_llm_update(
    enabled: str | None = Form(None),  # noqa: B008
    provider: str = Form("openai-compatible"),  # noqa: B008
    base_url: str = Form("http://localhost:11434/v1"),  # noqa: B008
    model: str = Form("llama3.1"),  # noqa: B008
    api_key_env: str = Form("WHY_LLM_API_KEY"),  # noqa: B008
    confirm_before_send: str = Form("remote"),  # noqa: B008
    max_input_commands: int = Form(200),  # noqa: B008
    session_id: str = Form(""),  # noqa: B008
) -> RedirectResponse:
    cfg = load_config()
    cfg["llm"].update(
        {
            "enabled": enabled == "1",
            "provider": provider,
            "base_url": base_url,
            "model": model,
            "api_key_env": api_key_env,
            "confirm_before_send": confirm_before_send,
            # The template's min="1" is client-side only.
            "max_input_commands": max(1, max_input_commands),
        }
    )
    write_config(cfg)
    if session_id:
        return RedirectResponse(url=f"/sessions/{session_id}", status_code=303)
    return RedirectResponse(url="/settings/llm", status_code=303)
