from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from why import store
from why.web.deps import get_db, get_presentation
from why.web.templates_env import make_env

router = APIRouter()
_env = make_env()


@router.get("/review", response_class=HTMLResponse)
def review_index(
    request: Request,
    db: Path = Depends(get_db),  # noqa: B008
    pres: dict[str, Any] = Depends(get_presentation),  # noqa: B008
) -> HTMLResponse:
    pending = store.list_skipped(db)
    if not pending:
        tmpl = _env.get_template("review.html")
        return HTMLResponse(tmpl.render(
            request=request, current=None, remaining=0, pres=pres, review_count=0,
        ))
    current = pending[0]
    tmpl = _env.get_template("review.html")
    return HTMLResponse(tmpl.render(
        request=request, current=current, remaining=len(pending), pres=pres,
        review_count=len(pending),
    ))


@router.post("/review/{install_id}")
def review_submit(
    install_id: int,
    display_name: str = Form(""),  # noqa: B008
    what_it_does: str = Form(""),  # noqa: B008
    project: str = Form(""),  # noqa: B008
    why: str = Form(""),  # noqa: B008
    disposition: str = Form(""),  # noqa: B008
    notes: str = Form(""),  # noqa: B008
    skip: str = Form(""),  # noqa: B008
    db: Path = Depends(get_db),  # noqa: B008
) -> RedirectResponse:
    if skip:
        return RedirectResponse(url="/review", status_code=303)
    if project:
        store.upsert_project(db, project)
    store.update_install(
        db, install_id,
        display_name=display_name or None,
        what_it_does=what_it_does or None,
        project=project or None,
        why=why or None,
        disposition=disposition or None,
        notes=notes or None,
        metadata_complete=1,
    )
    return RedirectResponse(url="/review", status_code=303)
