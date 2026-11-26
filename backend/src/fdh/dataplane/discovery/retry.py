"""Retry policy common to every platform (spec FDH-001-NFR-01). Pure functions."""

import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
BACKOFF_SECONDS = (1.0, 2.0, 4.0)
_DELAY_SECONDS = re.compile(r"\d{1,9}")


def parse_retry_after(value: str | None, *, now: datetime) -> float | None:
    """Seconds requested by a ``Retry-After`` header, as a delay or an HTTP date.

    An absent or unreadable value is unknown and returns ``None``.
    """
    if value is None:
        return None
    value = value.strip()
    if _DELAY_SECONDS.fullmatch(value):
        return float(value)
    try:
        moment = parsedate_to_datetime(value)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        return max(0.0, (moment - now).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


def backoff_delay(retry_number: int, retry_after: float | None) -> float:
    """Wait before retry ``retry_number`` (from 1), never shorter than the provider asks."""
    base = BACKOFF_SECONDS[min(retry_number, len(BACKOFF_SECONDS)) - 1]
    return max(base, retry_after or 0.0)
