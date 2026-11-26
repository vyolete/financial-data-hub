"""What discovery learns about a dataset. Absent values stay unknown."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class DatasetDates:
    created_at: datetime | None = None
    published_at: datetime | None = None
    metadata_updated_at: datetime | None = None
    data_updated_at: datetime | None = None
    updated_at: datetime | None = None  # declared without a precise meaning


@dataclass(frozen=True)
class AccessLocator:
    kind: str  # open vocabulary
    url: str  # verbatim; the core decides its validity
    source_field: str


@dataclass(frozen=True)
class DeclaredLicense:
    name: str | None = None  # verbatim, never a permission
    url: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class DiscoveredDataset:
    external_id: str
    title: str
    description: str | None = None
    publisher: str | None = None
    official_url: str | None = None
    categories: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    data_sources: tuple[str, ...] = ()
    licenses: tuple[DeclaredLicense, ...] = ()
    citation_requirement: str | None = None
    dates: DatasetDates = field(default_factory=DatasetDates)
    locators: tuple[AccessLocator, ...] = ()

    def __post_init__(self) -> None:
        if not self.external_id.strip() or not self.title.strip():
            raise ValueError("a dataset requires an external id and a title")


@dataclass(frozen=True)
class RejectedRecord:
    external_id: str | None
    # "missing_id", "missing_title", "unexpected_type", "unexpected_domain" or "malformed"
    reason: str
