from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from why import store
from why.web.deps import get_db, get_presentation
from why.web.filters import parse_query
from why.web.templates_env import make_env

router = APIRouter()
_env = make_env()

_DISPOSITIONS = ["doc", "setup", "experimental", "remove", "ignore"]


def _stale_count(db: Path) -> int:
    return len(store.stale_review_queue(db))


def _devices(db: Path) -> list[Any]:
    d = store.get_solo_device(db)
    return [d] if d else []


def _common_ctx(request: Request, db: Path, pres: dict[str, Any]) -> dict[str, Any]:
    state = parse_query(request.query_params)

    # Route rows depending on view=stale
    if state.view == "stale":
        rows: list[store.Install] = store.stale_review_queue(db)
    elif state.q:
        rows = store.search_installs(db, state.q)
    else:
        rows = store.list_installs(db, state.to_install_filters())

    projects = store.list_projects(db)
    managers = sorted(store.stats_by_manager(db).keys()) or list(pres.keys())
    devices = _devices(db)

    # Tab counts
    by_disp = store.stats_by_disposition(db)
    total_count = sum(by_disp.values())
    stale_count = _stale_count(db)

    def sort_link(col: str) -> str:
        params = dict(request.query_params)
        params["order_by"] = col
        flipped = state.order_by == col and state.order_dir == "desc"
        params["order_dir"] = "asc" if flipped else "desc"
        return urlencode(params)

    def tab_link(tab: str) -> str:
        """Build a URL for a tab preserving manager/project/device/q/sort."""
        params: dict[str, str] = {}
        for key in ("manager", "project", "device", "q", "order_by", "order_dir"):
            v = request.query_params.get(key)
            if v:
                params[key] = v
        if tab == "all":
            pass  # clear disposition and view
        elif tab == "stale":
            params["view"] = "stale"
        else:
            params["disposition"] = tab
        return urlencode(params)

    disp_pres = pres.get("disposition", {})
    tabs = [
        {"key": "all", "label": "All", "count": total_count},
        *[
            {
                "key": d,
                "label": disp_pres.get(d, {}).get("label", d.capitalize()),
                "count": by_disp.get(d, 0),
            }
            for d in _DISPOSITIONS
        ],
        {"key": "stale", "label": "Stale", "count": stale_count},
    ]

    # Active tab key
    if state.view == "stale":
        active_tab = "stale"
    elif state.disposition:
        active_tab = state.disposition
    else:
        active_tab = "all"

    return {
        "rows": rows,
        "filters": state,
        "q": state.q,
        "projects": projects,
        "managers": managers,
        "devices": devices,
        "pres": pres,
        "review_count": len(store.list_skipped(db)),
        "sort_link": sort_link,
        "tab_link": tab_link,
        "tabs": tabs,
        "active_tab": active_tab,
    }


@router.get("/installs", response_class=HTMLResponse)
def installs_page(
    request: Request,
    db: Path = Depends(get_db),  # noqa: B008
    pres: dict[str, Any] = Depends(get_presentation),  # noqa: B008
) -> HTMLResponse:
    ctx = _common_ctx(request, db, pres)
    return HTMLResponse(_env.get_template("installs.html").render(request=request, **ctx))


@router.get("/installs/table", response_class=HTMLResponse)
def installs_table(
    request: Request,
    db: Path = Depends(get_db),  # noqa: B008
    pres: dict[str, Any] = Depends(get_presentation),  # noqa: B008
) -> HTMLResponse:
    ctx = _common_ctx(request, db, pres)
    return HTMLResponse(_env.get_template("installs_table.html").render(request=request, **ctx))


# Bulk endpoints MUST be declared BEFORE /installs/{install_id} to avoid
# FastAPI matching "bulk" as an integer path param.

@router.post("/installs/bulk", response_class=HTMLResponse)
def installs_bulk_update(
    request: Request,
    selected: list[int] = Form(default=[]),  # noqa: B008
    disposition: str = Form(""),  # noqa: B008
    db: Path = Depends(get_db),  # noqa: B008
    pres: dict[str, Any] = Depends(get_presentation),  # noqa: B008
) -> HTMLResponse:
    if disposition and selected:
        for iid in selected:
            with contextlib.suppress(KeyError, ValueError):
                store.update_install(db, iid, disposition=disposition)
    ctx = _common_ctx(request, db, pres)
    return HTMLResponse(_env.get_template("installs_table.html").render(request=request, **ctx))


@router.post("/installs/bulk/delete", response_class=HTMLResponse)
def installs_bulk_delete(
    request: Request,
    selected: list[int] = Form(default=[]),  # noqa: B008
    db: Path = Depends(get_db),  # noqa: B008
    pres: dict[str, Any] = Depends(get_presentation),  # noqa: B008
) -> HTMLResponse:
    for iid in selected:
        with contextlib.suppress(Exception):
            store.soft_delete_install(db, iid)
    ctx = _common_ctx(request, db, pres)
    return HTMLResponse(_env.get_template("installs_table.html").render(request=request, **ctx))


def _row_ctx(db: Path, pres: dict[str, Any], install_id: int) -> dict[str, Any] | None:
    r = store.get_install(db, install_id)
    if not r:
        return None
    return {"r": r, "pres": pres, "projects": store.list_projects(db), "manager": r.manager}


@router.get("/installs/{install_id}/edit", response_class=HTMLResponse)
def install_edit(
    request: Request,
    install_id: int,
    db: Path = Depends(get_db),  # noqa: B008
    pres: dict[str, Any] = Depends(get_presentation),  # noqa: B008
) -> HTMLResponse:
    ctx = _row_ctx(db, pres, install_id)
    if ctx is None:
        return HTMLResponse("Not found", status_code=404)
    return HTMLResponse(_env.get_template("install_edit.html").render(request=request, **ctx))


@router.get("/installs/{install_id}/row", response_class=HTMLResponse)
def install_row(
    request: Request,
    install_id: int,
    db: Path = Depends(get_db),  # noqa: B008
    pres: dict[str, Any] = Depends(get_presentation),  # noqa: B008
) -> HTMLResponse:
    ctx = _row_ctx(db, pres, install_id)
    if ctx is None:
        return HTMLResponse("Not found", status_code=404)
    return HTMLResponse(_env.get_template("install_row.html").render(request=request, **ctx))


@router.post("/installs/{install_id}", response_class=HTMLResponse)
def install_update(
    request: Request,
    install_id: int,
    display_name: str = Form(""),  # noqa: B008
    what_it_does: str = Form(""),  # noqa: B008
    project: str = Form(""),  # noqa: B008
    why: str = Form(""),  # noqa: B008
    disposition: str = Form(""),  # noqa: B008
    notes: str = Form(""),  # noqa: B008
    metadata_complete: str = Form("1"),  # noqa: B008
    db: Path = Depends(get_db),  # noqa: B008
    pres: dict[str, Any] = Depends(get_presentation),  # noqa: B008
) -> HTMLResponse:
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
    if ctx is None:
        return HTMLResponse("Not found", status_code=404)
    return HTMLResponse(
        _env.get_template("install_row.html").render(request=request, **ctx),
        headers={"HX-Trigger": "closeEditModal"},
    )
