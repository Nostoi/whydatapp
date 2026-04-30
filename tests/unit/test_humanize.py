from __future__ import annotations

from datetime import UTC, datetime, timedelta

from why.humanize import time_ago


def _iso(delta_secs: float) -> str:
    """Return an ISO timestamp `delta_secs` seconds ago from now."""
    when = datetime.now(UTC) - timedelta(seconds=delta_secs)
    return when.isoformat()


def test_none_returns_never() -> None:
    assert time_ago(None) == "never"


def test_empty_string_returns_never() -> None:
    assert time_ago("") == "never"


def test_invalid_string_returns_never() -> None:
    assert time_ago("not-a-date") == "never"


def test_under_60s_is_just_now() -> None:
    assert time_ago(_iso(30)) == "just now"


def test_exactly_59s_is_just_now() -> None:
    assert time_ago(_iso(59)) == "just now"


def test_60s_is_minutes() -> None:
    result = time_ago(_iso(60))
    assert result.endswith("m ago")


def test_90s_is_1m_ago() -> None:
    assert time_ago(_iso(90)) == "1m ago"


def test_3600s_boundary_is_hours() -> None:
    # exactly 1 hour → "1h ago"
    result = time_ago(_iso(3600))
    assert result == "1h ago"


def test_2h_ago() -> None:
    assert time_ago(_iso(2 * 3600)) == "2h ago"


def test_24h_boundary_is_days() -> None:
    result = time_ago(_iso(86400))
    assert result == "1d ago"


def test_3d_ago() -> None:
    assert time_ago(_iso(3 * 86400)) == "3d ago"


def test_7d_boundary_is_weeks() -> None:
    result = time_ago(_iso(7 * 86400))
    assert result == "1w ago"


def test_2w_ago() -> None:
    assert time_ago(_iso(14 * 86400)) == "2w ago"


def test_30d_boundary_is_months() -> None:
    result = time_ago(_iso(30 * 86400))
    assert result == "1mo ago"


def test_2mo_ago() -> None:
    assert time_ago(_iso(60 * 86400)) == "2mo ago"


def test_365d_boundary_is_years() -> None:
    result = time_ago(_iso(365 * 86400))
    assert result == "1y ago"


def test_2y_ago() -> None:
    assert time_ago(_iso(730 * 86400)) == "2y ago"


def test_naive_datetime_handled_gracefully() -> None:
    # naive ISO (no tz info) should not crash
    naive = (datetime.now(UTC) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S")
    result = time_ago(naive)
    assert "d ago" in result or result == "just now"
