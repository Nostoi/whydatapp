from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from why.store import InstallFilters

_ALLOWED_ORDER = {"installed_at", "manager", "project", "disposition", "display_name", "id"}


@dataclass(frozen=True)
class FilterState:
    disposition: str | None
    project: str | None
    manager: str | None
    device_id: str | None
    incomplete_only: bool
    q: str
    order_by: str
    order_dir: str
    limit: int
    offset: int

    def to_install_filters(self) -> InstallFilters:
        return InstallFilters(
            disposition=self.disposition,
            project=self.project,
            manager=self.manager,
            device_id=self.device_id,
            incomplete_only=self.incomplete_only,
            limit=self.limit,
            offset=self.offset,
            order_by=self.order_by,
            order_dir=self.order_dir,
        )


def parse_query(qp: Mapping[str, str]) -> FilterState:
    def _opt(name: str) -> str | None:
        v = qp.get(name)
        return v.strip() or None if v else None

    order_by = qp.get("order_by", "installed_at")
    if order_by not in _ALLOWED_ORDER:
        order_by = "installed_at"
    order_dir = qp.get("order_dir", "desc")
    if order_dir not in ("asc", "desc"):
        order_dir = "desc"

    return FilterState(
        disposition=_opt("disposition"),
        project=_opt("project"),
        manager=_opt("manager"),
        device_id=_opt("device"),
        incomplete_only=qp.get("incomplete") == "1",
        q=qp.get("q", "").strip(),
        order_by=order_by,
        order_dir=order_dir,
        limit=int(qp.get("limit") or 100),
        offset=int(qp.get("offset") or 0),
    )
