"""What the control plane knows about discovery runs and their provenance."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from fdh.domain.datasets import DiscoveredDataset
from fdh.domain.status import RunStatus


class RunInProgress(Exception):
    """Another run holds the source. No run is created and nothing is requested."""


@dataclass(frozen=True)
class RunError:
    """A sanitized failure: a code and a fixed message, never URLs, bodies or secrets."""

    code: str
    message: str
    query_index: int | None = None
    http_status: int | None = None
    attempts: int | None = None


@dataclass(frozen=True)
class ObservedPage:
    """One page of results and where it came from. It is stored as a whole or not at all."""

    run_id: UUID
    source_id: str
    query_index: int
    source_url: str
    request_summary: Mapping[str, Any]
    observed_at: datetime
    datasets: tuple[DiscoveredDataset, ...]
    rejected: int
    total_declared: int | None


@dataclass(frozen=True)
class RunCounts:
    pages_processed: int = 0
    received: int = 0  # every record received, repetitions and rejections included
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    rejected: int = 0
    failures: int = 0

    @property
    def valid(self) -> int:
        """Distinct valid datasets recovered by the run."""
        return self.created + self.updated + self.unchanged


@dataclass(frozen=True)
class QueryRecord:
    query_index: int
    term: str | None
    filters: Mapping[str, str]
    pages_processed: int
    total_declared: int | None
    truncated: bool


@dataclass(frozen=True)
class RunRecord:
    run_id: UUID
    source_id: str
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None
    counts: RunCounts
    errors: tuple[RunError, ...]
    queries: tuple[QueryRecord, ...]
