"""A configured discovery source."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

from fdh.domain.permissions import Permission

# Platforms the product knows about; an adapter may not be available yet.
KNOWN_PLATFORMS = frozenset({"socrata", "data360"})


@dataclass(frozen=True)
class DiscoveryQuery:
    term: str | None = None
    filters: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DiscoveryLimits:
    page_size: int = 100
    max_pages: int = 5  # per query
    attempt_timeout_s: float = 10.0  # deadline of each attempt
    max_retries: int = 3  # additional to the first attempt
    max_retry_after_s: int = 60


@dataclass(frozen=True)
class PublicationDecision:
    """Whether the metadata of a source may be published, and who decided it."""

    value: Permission = Permission.UNDETERMINED
    declared_by: str | None = None
    declared_on: date | None = None
    evidence: str | None = None

    def __post_init__(self) -> None:
        if self.value is not Permission.UNDETERMINED and not self.is_audited:
            raise ValueError("a decision requires declared_by, declared_on and evidence")

    @property
    def is_audited(self) -> bool:
        return bool(
            self.declared_by
            and self.declared_by.strip()
            and self.declared_on
            and self.evidence
            and self.evidence.strip()
        )


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    provider: str
    platform: str
    base_url: str
    allowed_hosts: tuple[str, ...]
    official_url: str
    verified_at: date
    queries: tuple[DiscoveryQuery, ...] = ()
    limits: DiscoveryLimits = field(default_factory=DiscoveryLimits)
    publication: PublicationDecision = field(default_factory=PublicationDecision)
    attribution: str | None = None
    access_conditions: str | None = None
    redistribution_conditions: str | None = None
    license_name: str | None = None
    license_url: str | None = None
    terms_url: str | None = None
    terms_checked_on: date | None = None
    options: Mapping[str, str] = field(default_factory=dict)
