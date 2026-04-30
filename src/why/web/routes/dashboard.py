from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from why import store
from why.web.deps import get_db, get_presentation
from why.web.templates_env import make_env

router = APIRouter()
_env = make_env()


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db=Depends(get_db), pres=Depends(get_presentation)):
    ctx = {
        "by_disposition": store.stats_by_disposition(db),
        "by_manager": store.stats_by_manager(db),
        "by_project": store.stats_by_project(db, limit=10),
        "per_month": store.installs_per_month(db, months=12),
        "stale": store.stale_review_queue(db),
        "review_count": len(store.list_skipped(db)),
        "pres": pres,
    }
    return HTMLResponse(_env.get_template("dashboard.html").render(request=request, **ctx))
