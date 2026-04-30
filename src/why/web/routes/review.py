from __future__ import annotations

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from why import store
from why.web.deps import get_db, get_presentation
from why.web.templates_env import make_env

router = APIRouter()
_env = make_env()


@router.get("/review", response_class=HTMLResponse)
def review_index(db=Depends(get_db), pres=Depends(get_presentation)):
    pending = store.list_skipped(db)
    if not pending:
        tmpl = _env.get_template("review.html")
        return HTMLResponse(tmpl.render(current=None, remaining=0, pres=pres, review_count=0))
    current = pending[0]
    tmpl = _env.get_template("review.html")
    return HTMLResponse(tmpl.render(
        current=current, remaining=len(pending), pres=pres,
        review_count=len(pending),
    ))


@router.post("/review/{install_id}")
def review_submit(
    install_id: int,
    display_name: str = Form(""),
    what_it_does: str = Form(""),
    project: str = Form(""),
    why: str = Form(""),
    disposition: str = Form(""),
    notes: str = Form(""),
    skip: str = Form(""),
    db=Depends(get_db),
):
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
