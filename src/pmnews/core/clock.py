"""Single source of 'now'. All timestamps are timezone-aware UTC; dates are UTC calendar days."""

from datetime import UTC, date, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_today() -> date:
    return utc_now().date()


def parse_iso_utc(value: str) -> datetime:
    """Parse an ISO-8601 string; naive values are treated as UTC."""
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def from_unix(seconds: float) -> datetime:
    return datetime.fromtimestamp(seconds, UTC)
