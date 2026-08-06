import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def configured_timezone() -> ZoneInfo:
    name = os.getenv("HCP_TIMEZONE", "America/New_York")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("America/New_York")


def parse_timestamp(value) -> datetime | None:
    if value in {None, "", "never"}:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def format_dashboard_timestamp(value, tz: ZoneInfo | None = None) -> str:
    dt = parse_timestamp(value)
    if dt is None:
        return "never"
    local = dt.astimezone(tz or configured_timezone()).replace(second=0, microsecond=0)
    hour = local.strftime("%I").lstrip("0") or "12"
    suffix = local.strftime("%p")
    abbreviation = local.tzname() or ""
    return f"{local:%b} {local.day}, {local.year} · {hour}:{local:%M} {suffix} {abbreviation}".strip()


def format_relative_freshness(value, now: datetime | None = None, tz: ZoneInfo | None = None) -> str:
    dt = parse_timestamp(value)
    if dt is None:
        return "No successful update yet"
    zone = tz or configured_timezone()
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    local_dt = dt.astimezone(zone)
    local_now = current.astimezone(zone)
    delta = local_now - local_dt
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "Scheduled for the future"
    if seconds < 60:
        return "Updated just now"
    if seconds < 3600:
        minutes = seconds // 60
        return f"Updated {minutes} minute{'s' if minutes != 1 else ''} ago"
    if local_dt.date() == local_now.date():
        return "Updated today"
    if (local_now.date() - local_dt.date()).days == 1:
        return "Updated yesterday"
    days = (local_now.date() - local_dt.date()).days
    return f"Updated {days} days ago"


def with_freshness(value) -> str:
    formatted = format_dashboard_timestamp(value)
    if formatted == "never":
        return formatted
    return f"{formatted}\n{format_relative_freshness(value)}"
