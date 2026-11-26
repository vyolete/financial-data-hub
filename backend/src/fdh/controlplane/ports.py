"""Interfaces the control plane requires from persistence.

Later increments extend them together with their implementations.
"""

from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import date
from typing import Any, Protocol
from uuid import UUID

from fdh.controlplane.runs import ObservedPage, RunCounts, RunError, RunRecord
from fdh.controlplane.sources import RegisteredSource, SyncPlan
from fdh.domain.permissions import Permission, ReviewStatus
from fdh.domain.sources import DiscoveryQuery
from fdh.domain.status import RunStatus

SyncPlanner = Callable[[Sequence[RegisteredSource]], SyncPlan]


class SourceRepository(Protocol):
    async def synchronise(self, planner: SyncPlanner) -> SyncPlan:
        """Read, plan and apply in one transaction."""
        ...


class CatalogRepository(Protocol):
    async def store_page(self, page: ObservedPage) -> None:
        """Store datasets, locators, provenance and counts of a page in one transaction."""
        ...


class RunRepository(Protocol):
    def source_lock(self, source_id: str) -> AbstractAsyncContextManager[None]:
        """Hold the source for one run. Raises ``RunInProgress`` when it is taken."""
        ...

    async def close_abandoned(self, source_id: str, error: RunError) -> int:
        """Finish runs left running. Only valid while holding the source."""
        ...

    async def start(
        self, source_id: str, parameters: Mapping[str, Any], queries: Sequence[DiscoveryQuery]
    ) -> UUID: ...

    async def record_failure(self, run_id: UUID, error: RunError) -> None: ...

    async def mark_truncated(self, run_id: UUID, query_index: int) -> None: ...

    async def counts(self, run_id: UUID) -> RunCounts: ...

    async def finish(self, run_id: UUID, status: RunStatus) -> None: ...

    async def get(self, run_id: UUID) -> RunRecord: ...

    async def recent(self, source_id: str | None, limit: int) -> Sequence[RunRecord]:
        """Latest runs first."""
        ...


class QueryRepository(Protocol):
    async def search(
        self,
        *,
        text: str | None,
        provider: str | None,
        category: str | None,
        page: int,
        page_size: int,
    ) -> tuple[Sequence[Any], int]: ...


class DecisionRepository(Protocol):
    async def record_review(
        self,
        source_id: str,
        external_id: str,
        status: ReviewStatus | None,
        extraction: Permission | None,
        redistribution: Permission | None,
        *,
        evidence: str,
        decided_by: str,
        decided_on: date,
    ) -> None: ...
