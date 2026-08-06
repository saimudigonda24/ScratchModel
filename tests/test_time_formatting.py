import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frontend"))

from time_utils import format_dashboard_timestamp, format_relative_freshness


def test_dashboard_timestamp_removes_seconds_and_microseconds():
    formatted = format_dashboard_timestamp("2026-08-06T13:21:25.863803+00:00", ZoneInfo("America/New_York"))

    assert formatted == "Aug 6, 2026 · 9:21 AM EDT"
    assert "25" not in formatted
    assert "863803" not in formatted


def test_dashboard_timestamp_uses_configured_timezone(monkeypatch):
    monkeypatch.setenv("HCP_TIMEZONE", "America/Los_Angeles")

    assert format_dashboard_timestamp("2026-08-06T13:21:25+00:00") == "Aug 6, 2026 · 6:21 AM PDT"


def test_missing_timestamp_is_manager_friendly():
    assert format_dashboard_timestamp(None) == "never"
    assert format_relative_freshness(None) == "No successful update yet"


def test_relative_freshness_minutes_today_yesterday():
    tz = ZoneInfo("America/New_York")

    assert (
        format_relative_freshness(
            "2026-08-06T13:17:00+00:00",
            now=datetime(2026, 8, 6, 13, 21, tzinfo=timezone.utc),
            tz=tz,
        )
        == "Updated 4 minutes ago"
    )
    assert (
        format_relative_freshness(
            "2026-08-06T11:00:00+00:00",
            now=datetime(2026, 8, 6, 13, 21, tzinfo=timezone.utc),
            tz=tz,
        )
        == "Updated today"
    )
    assert (
        format_relative_freshness(
            "2026-08-05T18:00:00+00:00",
            now=datetime(2026, 8, 6, 13, 21, tzinfo=timezone.utc),
            tz=tz,
        )
        == "Updated yesterday"
    )
