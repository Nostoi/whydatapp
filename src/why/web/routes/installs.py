from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
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
    return HTMLResponse(_env.get_template("installs.html").render(**ctx))


@router.get("/installs/table", response_class=HTMLResponse)
def installs_table(request: Request, db=Depends(get_db), pres=Depends(get_presentation)):
    ctx = _common_ctx(request, db, pres)
    return HTMLResponse(_env.get_template("installs_table.html").render(**ctx))
