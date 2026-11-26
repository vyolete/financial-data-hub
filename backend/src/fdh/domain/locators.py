"""Syntactic verification of access locators. No locator is ever requested here."""

from enum import StrEnum
from urllib.parse import urlsplit


class LocatorStatus(StrEnum):
    UNVERIFIED = "unverified"
    INVALID = "invalid"


def is_https_url(url: str) -> bool:
    """Whether ``url`` is an absolute HTTPS URL with a host and without credentials."""
    if not url or any(char.isspace() or not char.isprintable() for char in url):
        return False
    try:
        parts = urlsplit(url)
        _ = parts.port  # raises ValueError when out of range
    except ValueError:
        return False
    return (
        parts.scheme == "https"
        and bool(parts.hostname)
        and parts.username is None
        and parts.password is None
    )


def locator_status(url: str) -> LocatorStatus:
    return LocatorStatus.UNVERIFIED if is_https_url(url) else LocatorStatus.INVALID


def usable_for_extraction(status: LocatorStatus) -> bool:
    """An invalid locator cannot be used until a corrected version passes validation.

    Extraction additionally requires an explicit permission on the dataset.
    """
    return status is not LocatorStatus.INVALID
