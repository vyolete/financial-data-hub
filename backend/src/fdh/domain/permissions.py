"""Permissions and review states. Nothing is permitted by default."""

from enum import StrEnum


class Permission(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    UNDETERMINED = "undetermined"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    RESTRICTED = "restricted"


def metadata_visible(publication: Permission, review: ReviewStatus) -> bool:
    """A dataset restriction always prevails over the permission of its source."""
    return publication is Permission.ALLOWED and review is not ReviewStatus.RESTRICTED
