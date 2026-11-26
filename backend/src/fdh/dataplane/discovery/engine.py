"""Discovery of one source, common to every platform (plan.md, "Motor de descubrimiento").

The engine knows the adapter contract and the control plane interfaces; it knows no platform,
database or API. The caller validates the configuration and synchronises the sources first.
"""

import logging
import time
from collections import Counter
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from fdh.controlplane.ports import CatalogRepository, RunRepository
from fdh.controlplane.runs import ObservedPage, RunError, RunMetrics, RunRecord
from fdh.dataplane.connectors.contract import (
    AdapterContext,
    DiscoveryAdapter,
    HttpRequest,
    InvalidResponse,
)
from fdh.dataplane.discovery.http import Classify, RequestFailed, RequestResult
from fdh.domain.sources import DiscoveryQuery, SourceDefinition
from fdh.domain.status import final_status

log = logging.getLogger(__name__)

INTERRUPTED = RunError("interrupted", "the run ended without recording its outcome")


class RequestSender(Protocol):
    requests_sent: int

    async def execute(self, request: HttpRequest, classify: Classify) -> RequestResult: ...


@dataclass(frozen=True)
class RunSummary:
    record: RunRecord
    abandoned_closed: int


@dataclass
class _Progress:
    run_id: UUID
    sender: RequestSender
    rejections: Counter[str]
    persistence_s: float = 0.0


def _parameters(source: SourceDefinition) -> dict[str, Any]:
    """What the run was asked to do. A source definition holds no secrets."""
    return {
        "base_url": source.base_url,
        "options": dict(source.options),
        "limits": asdict(source.limits),
        "queries": [{"term": q.term, "filters": dict(q.filters)} for q in source.queries],
    }


class DiscoveryEngine:
    def __init__(
        self,
        *,
        runs: RunRepository,
        catalog: CatalogRepository,
        sender_factory: Callable[[SourceDefinition], RequestSender],
        run_scope: Callable[[str], AbstractContextManager[None]] = lambda _: nullcontext(),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        timer: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._runs = runs
        self._catalog = catalog
        self._sender_factory = sender_factory
        self._run_scope = run_scope
        self._clock = clock
        self._timer = timer

    async def discover(self, source: SourceDefinition, adapter: DiscoveryAdapter) -> RunSummary:
        """Run every configured query of a source. Raises ``RunInProgress``."""
        async with self._runs.source_lock(source.source_id):
            started = self._timer()
            abandoned = await self._runs.close_abandoned(source.source_id, INTERRUPTED)
            run_id = await self._runs.start(source.source_id, _parameters(source), source.queries)
            with self._run_scope(str(run_id)):
                log.info(
                    "discovery run started",
                    extra={
                        "event": "run_started",
                        "source_id": source.source_id,
                        "abandoned_closed": abandoned,
                    },
                )
                progress = _Progress(run_id, self._sender_factory(source), Counter())
                for index, query in enumerate(source.queries):
                    if await self._query(source, adapter, index, query, progress):
                        break
                counts = await self._runs.counts(run_id)
                status = final_status(
                    valid=counts.valid, rejected=counts.rejected, failures=counts.failures
                )
                metrics = RunMetrics(
                    requests=progress.sender.requests_sent,
                    duration_ms=round((self._timer() - started) * 1000),
                    persistence_ms=round(progress.persistence_s * 1000),
                    rejection_reasons=dict(progress.rejections),
                )
                await self._runs.finish(run_id, status, metrics)
                record = await self._runs.get(run_id)
                log.info(
                    "discovery run finished",
                    extra={
                        "event": "run_finished",
                        "source_id": source.source_id,
                        "status": status.value,
                        # Nested: `created` is a reserved attribute of a log record.
                        "counts": {**asdict(counts), "unique": counts.valid},
                        "requests": metrics.requests,
                        "duration_ms": metrics.duration_ms,
                        "persistence_ms": metrics.persistence_ms,
                    },
                )
        return RunSummary(record, abandoned)

    async def _query(
        self,
        source: SourceDefinition,
        adapter: DiscoveryAdapter,
        index: int,
        query: DiscoveryQuery,
        progress: _Progress,
    ) -> bool:
        """Page through one query. Returns whether the whole run must stop."""
        context = AdapterContext(
            source.source_id, source.base_url, source.limits.page_size, source.options
        )
        cursor: str | None = None
        for _ in range(source.limits.max_pages):
            result: RequestResult | None = None
            try:
                request = adapter.build_request(context, query, cursor)
                result = await progress.sender.execute(request, adapter.classify)
                page = adapter.parse(context, request, result.response, cursor)
            except RequestFailed as error:
                await self._fail(
                    progress,
                    RunError(error.code, error.message, index, error.http_status, error.attempts),
                )
                return error.stop_run
            except InvalidResponse as error:
                await self._fail(
                    progress,
                    RunError(
                        "invalid_response",
                        str(error),  # adapters raise fixed messages
                        index,
                        result.response.status if result else None,
                        result.attempts if result else None,
                    ),
                )
                return False
            except Exception as error:
                # Only the type is logged: the message may carry content of the response.
                log.error(
                    "unexpected adapter error",
                    extra={"event": "adapter_error", "error_type": type(error).__name__},
                )
                await self._fail(
                    progress,
                    RunError("internal_error", "the response could not be processed", index),
                )
                return False

            before = self._timer()
            try:
                await self._catalog.store_page(
                    ObservedPage(
                        run_id=progress.run_id,
                        source_id=source.source_id,
                        query_index=index,
                        source_url=result.url,
                        request_summary={
                            "method": request.method,
                            "params": dict(request.params),
                            "json_body": None
                            if request.json_body is None
                            else dict(request.json_body),
                        },
                        observed_at=self._clock(),
                        datasets=page.datasets,
                        rejected=len(page.rejected),
                        total_declared=page.total_declared,
                    )
                )
            except Exception as error:
                # Database errors quote statements and values: log the type only.
                log.error(
                    "a page could not be stored",
                    extra={"event": "persistence_error", "error_type": type(error).__name__},
                )
                await self._fail(
                    progress,
                    RunError("persistence_error", "a page of results could not be stored", index),
                )
                return True
            finally:
                progress.persistence_s += self._timer() - before

            reasons = Counter(record.reason for record in page.rejected)
            progress.rejections.update(reasons)
            log.info(
                "page stored",
                extra={
                    "event": "page_stored",
                    "query_index": index,
                    "datasets": len(page.datasets),
                    "rejected": len(page.rejected),
                    "rejection_reasons": dict(reasons),
                    "total_declared": page.total_declared,
                    "attempts": result.attempts,
                },
            )
            cursor = page.next_cursor
            if cursor is None:
                return False
        # Results remain after the page limit: intentional, not an error.
        await self._runs.mark_truncated(progress.run_id, index)
        return False

    async def _fail(self, progress: _Progress, error: RunError) -> None:
        log.warning(
            "discovery query failed",
            extra={
                "event": "query_failed",
                "code": error.code,
                "query_index": error.query_index,
                "http_status": error.http_status,
                "attempts": error.attempts,
            },
        )
        await self._runs.record_failure(progress.run_id, error)
