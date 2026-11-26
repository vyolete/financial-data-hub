"""Interfaces the control plane requires from persistence.

Later increments extend them together with their implementations.
"""

from collections.abc import Callable, Sequence
from datetime import date
from typing import Any, Protocol
from uuid import UUID

from fdh.controlplane.sources import RegisteredSource, SyncPlan
from fdh.domain.datasets import DiscoveredDataset
from fdh.domain.permissions import Permission, ReviewStatus
from fdh.domain.sources import DiscoveryQuery
from fdh.domain.status import RunStatus

SyncPlanner = Callable[[Sequence[RegisteredSource]], SyncPlan]


class SourceRepository(Protocol):
    async def synchronise(self, planner: SyncPlanner) -> SyncPlan:
        """Read, plan and apply in one transaction."""
        ...


class CatalogRepository(Protocol):
    async def store_page(
        self,
        run_id: UUID,
        source_id: str,
        query_index: int,
        datasets: Sequence[DiscoveredDataset],
    ) -> None: ...


class RunRepository(Protocol):
    async def start(self, source_id: str, queries: Sequence[DiscoveryQuery]) -> UUID: ...

    async def finish(self, run_id: UUID, status: RunStatus) -> None: ...


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
