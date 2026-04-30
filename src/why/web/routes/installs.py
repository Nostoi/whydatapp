from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from why import store
from why.web.deps import get_db, get_presentation
from why.web.filters import parse_query
from why.web.templates_env import make_env

router = APIRouter()
_env = make_env()


def _stale_count(db) -> int:
    return len(store.list_skipped(db))


def _devices(db):
    d = store.get_solo_device(db)
    return [d] if d else []


def _common_ctx(request: Request, db, pres) -> dict:
    state = parse_query(request.query_params)
    rows = (
        store.search_installs(db, state.q) if state.q
        else store.list_installs(db, state.to_install_filters())
    )
    projects = store.list_projects(db)
    managers = sorted(store.stats_by_manager(db).keys()) or list(pres.keys())
    devices = _devices(db)

    def sort_link(col: str) -> str:
        params = dict(request.query_params)
        params["order_by"] = col
        params["order_dir"] = "asc" if state.order_by == col and state.order_dir == "desc" else "desc"
        return urlencode(params)

    return {
        "rows": rows,
        "filters": state,
        "q": state.q,
        "projects": projects,
        "managers": managers,
        "devices": devices,
        "pres": pres,
        "review_count": _stale_count(db),
        "sort_link": sort_link,
    }


@router.get("/installs", response_class=HTMLResponse)
def installs_page(request: Request, db=Depends(get_db), pres=Depends(get_presentation)):
    ctx = _common_ctx(request, db, pres)
    return HTMLResponse(_env.get_template("installs.html").render(request=request, **ctx))


@router.get("/installs/table", response_class=HTMLResponse)
def installs_table(request: Request, db=Depends(get_db), pres=Depends(get_presentation)):
    ctx = _common_ctx(request, db, pres)
    return HTMLResponse(_env.get_template("installs_table.html").render(request=request, **ctx))


def _row_ctx(db, pres, install_id: int) -> dict | None:
    r = store.get_install(db, install_id)
    if not r:
        return None
    return {"r": r, "pres": pres, "projects": store.list_projects(db), "manager": r.manager}


@router.get("/installs/{install_id}/edit", response_class=HTMLResponse)
def install_edit(request: Request, install_id: int, db=Depends(get_db), pres=Depends(get_presentation)):
    ctx = _row_ctx(db, pres, install_id)
    if ctx is None:
        return HTMLResponse("Not found", status_code=404)
    return HTMLResponse(_env.get_template("install_edit.html").render(request=request, **ctx))


@router.get("/installs/{install_id}/row", response_class=HTMLResponse)
def install_row(request: Request, install_id: int, db=Depends(get_db), pres=Depends(get_presentation)):
    ctx = _row_ctx(db, pres, install_id)
    if ctx is None:
        return HTMLResponse("Not found", status_code=404)
    return HTMLResponse(_env.get_template("install_row.html").render(request=request, **ctx))


@router.post("/installs/{install_id}", response_class=HTMLResponse)
def install_update(
    request: Request,
    install_id: int,
    display_name: str = Form(""),
    what_it_does: str = Form(""),
    project: str = Form(""),
    why: str = Form(""),
    disposition: str = Form(""),
    notes: str = Form(""),
    metadata_complete: str = Form("1"),
    db=Depends(get_db),
    pres=Depends(get_presentation),
):
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
        metadata_complete=int(metadata_complete or 0),
    )
    ctx = _row_ctx(db, pres, install_id)
    return HTMLResponse(_env.get_template("install_row.html").render(request=request, **ctx))
