from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from why import store
from why.web.deps import get_db, get_presentation, get_purposes
from why.web.templates_env import make_env

router = APIRouter()
_env = make_env()

_W = 400  # SVG viewBox width
_H = 40   # SVG viewBox height


def _build_sparkline_points(per_month: list[tuple[str, int]]) -> list[tuple[float, float]]:
    """Convert per-month counts (DESC order) to SVG (x, y) points for a sparkline.

    Returns points in chronological (ASC) order for left-to-right plotting.
    Returns empty list if fewer than 2 points.
    """
    # per_month is DESC; reverse to get chronological order
    ordered = list(reversed(per_month))
    n = len(ordered)
    if n < 1:
        return []
    counts = [c for _, c in ordered]
    min_c = min(counts)
    max_c = max(counts)
    # Pad a bit so the line doesn't touch the very top/bottom edge
    pad_y = _H * 0.1
    usable_h = _H - 2 * pad_y

    points: list[tuple[float, float]] = []
    for i, c in enumerate(counts):
        x = (i / max(n - 1, 1)) * _W
        y = _H / 2 if max_c == min_c else pad_y + (1.0 - (c - min_c) / (max_c - min_c)) * usable_h
        points.append((round(x, 2), round(y, 2)))
    return points


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(  # noqa: B008
    request: Request,
    db: Path = Depends(get_db),  # noqa: B008
    pres: dict[str, Any] = Depends(get_presentation),  # noqa: B008
) -> HTMLResponse:
    by_disposition = store.stats_by_disposition(db)
    by_manager = store.stats_by_manager(db)
    by_project = store.stats_by_project(db, limit=10)
    per_month = store.installs_per_month(db, months=12)
    stale = store.stale_review_queue(db)
    skipped = store.list_skipped(db)
    purposes = get_purposes(db)

    total_installs = sum(by_disposition.values())
    total_projects = len(by_project)
    stale_count = len(stale)

    sparkline_points = _build_sparkline_points(per_month)
    latest_month: tuple[str, int] | None = per_month[0] if per_month else None

    ctx: dict[str, Any] = {
        "by_disposition": by_disposition,
        "by_manager": by_manager,
        "by_project": by_project,
        "per_month": per_month,
        "stale": stale,
        "review_count": len(skipped),
        "pres": pres,
        "purposes": purposes,
        "total_installs": total_installs,
        "total_projects": total_projects,
        "stale_count": stale_count,
        "sparkline_points": sparkline_points,
        "latest_month": latest_month,
        "sparkline_w": _W,
        "sparkline_h": _H,
    }
    return HTMLResponse(_env.get_template("dashboard.html").render(request=request, **ctx))
