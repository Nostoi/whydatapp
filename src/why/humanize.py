from __future__ import annotations

from datetime import UTC, datetime


def time_ago(when_iso: str | None) -> str:
    """Coarse bucketed time-ago: '3d ago', '2w ago', '4mo ago', '1y ago'.

    Returns 'just now' for under 60s. Returns 'never' for None/empty input.
    """
    if not when_iso:
        return "never"

    try:
        when = datetime.fromisoformat(when_iso)
    except ValueError:
        return "never"

    # Ensure timezone-aware comparison.
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)

    now = datetime.now(UTC)
    delta_secs = (now - when).total_seconds()

    if delta_secs < 60:
        return "just now"
    if delta_secs < 3600:
        mins = int(delta_secs // 60)
        return f"{mins}m ago"
    if delta_secs < 86400:
        hours = int(delta_secs // 3600)
        return f"{hours}h ago"
    if delta_secs < 7 * 86400:
        days = int(delta_secs // 86400)
        return f"{days}d ago"
    if delta_secs < 30 * 86400:
        weeks = int(delta_secs // (7 * 86400))
        return f"{weeks}w ago"
    if delta_secs < 365 * 86400:
        months = int(delta_secs // (30 * 86400))
        return f"{months}mo ago"
    years = int(delta_secs // (365 * 86400))
    return f"{years}y ago"
