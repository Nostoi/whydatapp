from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from why import store
from why.markdown import to_markdown
from why.web.deps import get_db

router = APIRouter()


@router.get("/export")
def export(
    ids: str = Query(""),  # noqa: B008
    format: str = Query("md"),  # noqa: B008
    db: Path = Depends(get_db),  # noqa: B008
) -> Response:
    if not ids:
        return Response("ids required", status_code=400)
    rows = []
    for s in ids.split(","):
        try:
            inst = store.get_install(db, int(s))
        except ValueError:
            continue
        if inst:
            rows.append(inst)
    if format == "md":
        body = "\n".join(to_markdown(r) for r in rows)
        return Response(
            body,
            media_type="text/markdown",
            headers={"Content-Disposition": "attachment; filename=why-export.md"},
        )
    if format == "json":
        body = json.dumps([r.__dict__ for r in rows], indent=2, default=str)
        return Response(
            body,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=why-export.json"},
        )
    return Response("format must be md or json", status_code=400)
