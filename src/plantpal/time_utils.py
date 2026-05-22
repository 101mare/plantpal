"""Time helpers. All stored datetimes are *naive Berlin* time (Europe/Berlin)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")
_ISO = "%Y-%m-%dT%H:%M:%S"


def now_berlin() -> datetime:
    """Current wall-clock time in Berlin, as a naive datetime (no tzinfo)."""
    return datetime.now(BERLIN).replace(tzinfo=None, microsecond=0)


def today_berlin() -> date:
    """Current calendar date in Berlin."""
    return now_berlin().date()


def to_iso(dt: datetime) -> str:
    """Serialize a naive datetime to ISO-8601 (second precision, no tz suffix)."""
    return dt.replace(microsecond=0).strftime(_ISO)


def from_iso(value: str) -> datetime:
    """Parse an ISO-8601 string into a naive *Berlin* datetime.

    Internal rows are naive Berlin and parse as-is. Timezone-bearing strings
    (trailing ``Z`` or ``+hh:mm``, e.g. external API input) are converted to
    Berlin wall-clock before the tzinfo is dropped — never reinterpreted as local.
    """
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    dt = datetime.fromisoformat(cleaned)
    if dt.tzinfo is not None:
        dt = dt.astimezone(BERLIN).replace(tzinfo=None)
    return dt.replace(microsecond=0)


def parse_date(value: str) -> date:
    """Parse an ISO date (``YYYY-MM-DD``) or datetime string into a date."""
    return from_iso(value).date() if "T" in value else date.fromisoformat(value)
