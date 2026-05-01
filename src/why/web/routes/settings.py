from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from why import store
from why.web.deps import get_db, get_presentation
from why.web.templates_env import make_env

router = APIRouter()
_env = make_env()


def _ctx(db: Path, pres: dict[str, Any]) -> dict[str, Any]:
    return {
        "purposes": store.list_purposes(db),
        "pres": pres,
        "review_count": len(store.list_skipped(db)),
    }


@router.get("/settings/purposes", response_class=HTMLResponse)
def settings_purposes(
    request: Request,
    db: Path = Depends(get_db),  # noqa: B008
    pres: dict[str, Any] = Depends(get_presentation),  # noqa: B008
) -> HTMLResponse:
    return HTMLResponse(
        _env.get_template("settings_purposes.html").render(request=request, **_ctx(db, pres))
    )


@router.post("/settings/purposes", response_class=HTMLResponse)
def settings_purposes_add(
    request: Request,
    key: str = Form(...),  # noqa: B008
    label: str = Form(...),  # noqa: B008
    color: str = Form("#6b7280"),  # noqa: B008
    sort_order: int = Form(99),  # noqa: B008
    db: Path = Depends(get_db),  # noqa: B008
    pres: dict[str, Any] = Depends(get_presentation),  # noqa: B008
) -> HTMLResponse:
    error: str | None = None
    try:
        store.create_purpose(db, key=key, label=label, color=color, sort_order=sort_order)
    except Exception as e:
        error = str(e)
    ctx = _ctx(db, pres)
    ctx["error"] = error
    return HTMLResponse(
        _env.get_template("settings_purposes.html").render(request=request, **ctx),
        status_code=422 if error else 200,
    )


@router.post("/settings/purposes/{key}/edit", response_class=HTMLResponse)
def settings_purposes_edit(
    request: Request,
    key: str,
    label: str = Form(...),  # noqa: B008
    color: str = Form("#6b7280"),  # noqa: B008
    sort_order: int = Form(99),  # noqa: B008
    db: Path = Depends(get_db),  # noqa: B008
    pres: dict[str, Any] = Depends(get_presentation),  # noqa: B008
) -> HTMLResponse:
    error: str | None = None
    try:
        store.update_purpose(db, key, label=label, color=color, sort_order=sort_order)
    except (KeyError, ValueError) as e:
        error = str(e)
    ctx = _ctx(db, pres)
    ctx["error"] = error
    return HTMLResponse(
        _env.get_template("settings_purposes.html").render(request=request, **ctx),
        status_code=422 if error else 200,
    )


@router.post("/settings/purposes/{key}/delete")
def settings_purposes_delete(
    key: str,
    db: Path = Depends(get_db),  # noqa: B008
) -> RedirectResponse:
    with contextlib.suppress(KeyError, ValueError):
        store.delete_purpose(db, key)
    return RedirectResponse(url="/settings/purposes", status_code=303)
