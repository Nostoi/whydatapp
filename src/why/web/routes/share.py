from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from why import store
from why.markdown import to_markdown
from why.web.deps import get_db

router = APIRouter()


@router.post("/installs/{install_id}/share", response_class=PlainTextResponse)
def share(
    install_id: int,
    db: Path = Depends(get_db),  # noqa: B008
) -> PlainTextResponse:
    inst = store.get_install(db, install_id)
    if not inst:
        return PlainTextResponse("Not found", status_code=404)
    return PlainTextResponse(to_markdown(inst))
