from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from why.web.deps import get_db, get_presentation
from why.web.templates_env import make_env

router = APIRouter()
_env = make_env()


@router.get("/installs", response_class=HTMLResponse)
def installs_page(request: Request, db=Depends(get_db), pres=Depends(get_presentation)):
    tmpl = _env.get_template("installs.html")
    return HTMLResponse(tmpl.render(q=request.query_params.get("q", ""), review_count=0))
