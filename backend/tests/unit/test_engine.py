"""The discovery engine with a synthetic adapter and in-memory repositories.

AC-01, AC-02, AC-08 to AC-11, AC-30 and AC-32. Nothing here is real data.
"""

import io
import json
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from fdh.controlplane.runs import (
    ObservedPage,
    QueryRecord,
    RunCounts,
    RunError,
    RunInProgress,
    RunMetrics,
    RunRecord,
)
from fdh.dataplane.connectors.contract import (
    AdapterCapabilities,
    AdapterContext,
    DiscoveryPage,
    ErrorKind,
    HttpRequest,
    HttpResponse,
    InvalidResponse,
)
from fdh.dataplane.discovery.engine import DiscoveryEngine, RunSummary
from fdh.dataplane.discovery.http import RequestFailed, RequestResult
from fdh.domain.datasets import DiscoveredDataset, RejectedRecord
from fdh.domain.sources import DiscoveryLimits, DiscoveryQuery, SourceDefinition
from fdh.domain.status import RunStatus, final_status
from fdh.observability.logging import configure_logging, run_context

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def page(
    *ids: str, rejected: int = 0, next_cursor: str | None = None, total: int | None = None
) -> DiscoveryPage:
    return DiscoveryPage(
        tuple(DiscoveredDataset(i, f"Synthetic {i}") for i in ids),
        tuple(RejectedRecord(None, "missing_id") for _ in range(rejected)),
        total,
        next_cursor,
    )


class ScriptedAdapter:
    """Each term owns a script of pages or exceptions, consumed in order."""

    platform = "synthetic"
    capabilities = AdapterCapabilities(True, True, True)

    def __init__(self, script: Mapping[str, Sequence[object]]) -> None:
        self.script = {term: list(steps) for term, steps in script.items()}
        self.cursors: list[tuple[str, str | None]] = []

    def validate(self, context: AdapterContext, queries: tuple[DiscoveryQuery, ...]) -> None:
        return None

    def build_request(
        self, context: AdapterContext, query: DiscoveryQuery, cursor: str | None
    ) -> HttpRequest:
        assert query.term is not None
        self.cursors.append((query.term, cursor))
        return HttpRequest(
            "GET",
            context.base_url,
            {"q": query.term, "limit": str(context.page_size), "cursor": cursor or ""},
        )

    def classify(self, response: HttpResponse) -> ErrorKind | None:
        return None

    def parse(
        self,
        context: AdapterContext,
        request: HttpRequest,
        response: HttpResponse,
        cursor: str | None,
    ) -> DiscoveryPage:
        step = self.script[request.params["q"]].pop(0)
        if isinstance(step, Exception):
            raise step
        assert isinstance(step, DiscoveryPage)
        return step


class FakeSender:
    """Answers every request, or raises the failure scripted for its term."""

    def __init__(self, failures: Mapping[tuple[str, str], RequestFailed]) -> None:
        self.failures = failures
        self.requests: list[HttpRequest] = []
        self.requests_sent = 0

    async def execute(
        self, request: HttpRequest, classify: Callable[[HttpResponse], ErrorKind | None]
    ) -> RequestResult:
        self.requests.append(request)
        key = (request.params["q"], request.params["cursor"])
        if failure := self.failures.get(key):
            self.requests_sent += failure.attempts
            raise failure
        self.requests_sent += 1
        return RequestResult(HttpResponse(200, {}, b"{}"), 1, f"{request.url}?q={key[0]}")


@dataclass
class FakeStore:
    """Runs and catalog in memory, counting distinct datasets once per run."""

    locked: bool = False
    abandoned: int = 0
    fail_store: bool = False
    pages: list[ObservedPage] = field(default_factory=list)
    records: dict[UUID, RunRecord] = field(default_factory=dict)
    seen: set[str] = field(default_factory=set)
    parameters: Mapping[str, Any] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    @asynccontextmanager
    async def source_lock(self, source_id: str) -> AsyncIterator[None]:
        if self.locked:
            raise RunInProgress(source_id)
        self.events.append("lock")
        try:
            yield
        finally:
            self.events.append("unlock")

    async def close_abandoned(self, source_id: str, error: RunError) -> int:
        assert error.code == "interrupted"
        self.events.append("close_abandoned")
        return self.abandoned

    async def start(
        self, source_id: str, parameters: Mapping[str, Any], queries: Sequence[DiscoveryQuery]
    ) -> UUID:
        self.events.append("start")
        run_id = uuid4()
        self.parameters = parameters
        self.records[run_id] = RunRecord(
            run_id,
            source_id,
            RunStatus.RUNNING,
            NOW,
            None,
            RunCounts(),
            (),
            tuple(
                QueryRecord(i, q.term, dict(q.filters), 0, None, False)
                for i, q in enumerate(queries)
            ),
        )
        return run_id

    def _query(self, run_id: UUID, index: int, **changes: Any) -> None:
        record = self.records[run_id]
        queries = tuple(
            replace(q, **changes) if q.query_index == index else q for q in record.queries
        )
        self.records[run_id] = replace(record, queries=queries)

    async def store_page(self, observed: ObservedPage) -> None:
        if self.fail_store:
            raise OSError("synthetic database failure with private-value")
        self.pages.append(observed)
        record = self.records[observed.run_id]
        counts = record.counts
        new = {d.external_id for d in observed.datasets} - self.seen
        self.seen |= new
        self.records[observed.run_id] = replace(
            record,
            counts=replace(
                counts,
                pages_processed=counts.pages_processed + 1,
                received=counts.received + len(observed.datasets) + observed.rejected,
                created=counts.created + len(new),
                rejected=counts.rejected + observed.rejected,
            ),
        )
        query = record.queries[observed.query_index]
        self._query(
            observed.run_id,
            observed.query_index,
            pages_processed=query.pages_processed + 1,
            total_declared=observed.total_declared,
        )

    async def record_failure(self, run_id: UUID, error: RunError) -> None:
        record = self.records[run_id]
        self.records[run_id] = replace(
            record,
            counts=replace(record.counts, failures=record.counts.failures + 1),
            errors=(*record.errors, error),
        )

    async def mark_truncated(self, run_id: UUID, query_index: int) -> None:
        self._query(run_id, query_index, truncated=True)

    async def counts(self, run_id: UUID) -> RunCounts:
        return self.records[run_id].counts

    async def finish(self, run_id: UUID, status: RunStatus, metrics: RunMetrics) -> None:
        self.events.append("finish")
        self.records[run_id] = replace(
            self.records[run_id], status=status, finished_at=NOW, metrics=metrics
        )

    async def get(self, run_id: UUID) -> RunRecord:
        return self.records[run_id]

    async def recent(self, source_id: str | None, limit: int) -> Sequence[RunRecord]:
        return list(self.records.values())[:limit]


def source(*terms: str, max_pages: int = 5, page_size: int = 100) -> SourceDefinition:
    return SourceDefinition(
        source_id="synthetic",
        provider="Synthetic Provider",
        platform="synthetic",
        base_url="https://api.example.org/catalog",
        allowed_hosts=("api.example.org",),
        official_url="https://www.example.org",
        verified_at=date(2026, 1, 1),
        queries=tuple(DiscoveryQuery(t) for t in terms),
        limits=DiscoveryLimits(page_size=page_size, max_pages=max_pages),
    )


async def run(
    adapter: ScriptedAdapter,
    definition: SourceDefinition,
    store: FakeStore | None = None,
    sender: FakeSender | None = None,
) -> tuple[RunSummary, FakeStore, FakeSender]:
    store = store or FakeStore()
    sender = sender or FakeSender({})
    engine = DiscoveryEngine(
        runs=store,
        catalog=store,
        sender_factory=lambda _: sender,
        run_scope=run_context,
        clock=lambda: NOW,
    )
    return await engine.discover(definition, adapter), store, sender


async def test_follows_the_cursor_and_stops_without_more_results() -> None:
    adapter = ScriptedAdapter(
        {"a": [page("1", "2", next_cursor="c1", total=3), page("3", total=3)]}
    )
    summary, store, sender = await run(adapter, source("a"))
    assert adapter.cursors == [("a", None), ("a", "c1")]
    assert summary.record.status is RunStatus.SUCCEEDED
    assert summary.record.counts == RunCounts(pages_processed=2, received=3, created=3)
    assert summary.record.queries[0].truncated is False
    assert summary.record.queries[0].total_declared == 3
    assert summary.record.metrics.requests == len(sender.requests) == 2
    assert store.events == ["lock", "close_abandoned", "start", "finish", "unlock"]


async def test_the_page_limit_truncates_without_an_error() -> None:
    steps = [page(str(i), next_cursor=f"c{i}", total=900) for i in range(9)]
    summary, _, sender = await run(ScriptedAdapter({"a": steps}), source("a"))
    assert len(sender.requests) == 5
    assert summary.record.status is RunStatus.SUCCEEDED
    assert summary.record.counts.failures == 0
    query = summary.record.queries[0]
    assert (query.pages_processed, query.truncated, query.total_declared) == (5, True, 900)


async def test_limits_and_terms_come_from_the_configuration() -> None:
    adapter = ScriptedAdapter(
        {"x": [page("1", next_cursor="c")], "y": [page("2", next_cursor="c")]}
    )
    summary, _, sender = await run(adapter, source("x", "y", max_pages=1, page_size=7))
    assert [(r.params["q"], r.params["limit"]) for r in sender.requests] == [("x", "7"), ("y", "7")]
    assert [q.truncated for q in summary.record.queries] == [True, True]


async def test_provenance_of_each_page_is_passed_to_the_catalog() -> None:
    adapter = ScriptedAdapter({"a": [page("1")], "b": [page("1")]})
    summary, store, _ = await run(adapter, source("a", "b"))
    assert [p.query_index for p in store.pages] == [0, 1]
    first = store.pages[0]
    assert (first.run_id, first.source_id, first.observed_at) == (
        summary.record.run_id,
        "synthetic",
        NOW,
    )
    assert first.source_url == "https://api.example.org/catalog?q=a"
    assert first.request_summary == {
        "method": "GET",
        "params": {"q": "a", "limit": "100", "cursor": ""},
        "json_body": None,
    }
    assert summary.record.counts.created == 1
    assert summary.record.counts.received == 2
    assert store.parameters["queries"] == [
        {"term": "a", "filters": {}},
        {"term": "b", "filters": {}},
    ]
    assert store.parameters["limits"]["max_pages"] == 5


async def test_an_empty_search_succeeds() -> None:
    summary, _, _ = await run(ScriptedAdapter({"a": [page(total=0)]}), source("a"))
    assert summary.record.status is RunStatus.SUCCEEDED
    assert summary.record.counts.received == 0


async def test_rejected_records_with_valid_ones_make_the_run_partial() -> None:
    summary, _, _ = await run(ScriptedAdapter({"a": [page("1", rejected=2)]}), source("a"))
    assert summary.record.status is RunStatus.PARTIAL
    assert (summary.record.counts.rejected, summary.record.counts.received) == (2, 3)
    assert summary.record.metrics.rejection_reasons == {"missing_id": 2}


async def test_only_rejected_records_make_the_run_failed() -> None:
    summary, _, _ = await run(ScriptedAdapter({"a": [page(rejected=2)]}), source("a"))
    assert summary.record.status is RunStatus.FAILED


def failed(code: str = "http_error", *, attempts: int = 4, stop: bool = False) -> RequestFailed:
    return RequestFailed(
        code, "synthetic failure", http_status=503, attempts=attempts, stop_run=stop
    )


async def test_a_failed_query_does_not_stop_the_following_ones() -> None:
    adapter = ScriptedAdapter({"a": [page("1", next_cursor="c1")], "b": [page("2")]})
    sender = FakeSender({("a", "c1"): failed()})
    summary, _, _ = await run(adapter, source("a", "b"), sender=sender)
    assert summary.record.status is RunStatus.PARTIAL
    assert summary.record.counts.created == 2
    assert summary.record.errors == (
        RunError("http_error", "synthetic failure", query_index=0, http_status=503, attempts=4),
    )
    assert summary.record.queries[0].truncated is False
    assert summary.record.metrics.requests == 6


async def test_failures_without_valid_records_make_the_run_failed() -> None:
    adapter = ScriptedAdapter({"a": [], "b": []})
    sender = FakeSender({("a", ""): failed(), ("b", ""): failed()})
    summary, store, _ = await run(adapter, source("a", "b"), sender=sender)
    assert summary.record.status is RunStatus.FAILED
    assert summary.record.counts.failures == 2
    assert store.pages == []


async def test_a_long_retry_after_stops_the_whole_run() -> None:
    adapter = ScriptedAdapter({"a": [page("1", next_cursor="c1")], "b": [page("2")]})
    sender = FakeSender({("a", "c1"): failed("retry_after_too_long", attempts=1, stop=True)})
    summary, _, _ = await run(adapter, source("a", "b"), sender=sender)
    assert [r.params["q"] for r in sender.requests] == ["a", "a"]
    assert summary.record.status is RunStatus.PARTIAL
    assert summary.record.queries[1].pages_processed == 0


async def test_an_uninterpretable_response_is_a_failure_of_its_query() -> None:
    adapter = ScriptedAdapter({"a": [InvalidResponse("results is not a list")], "b": [page("2")]})
    summary, _, _ = await run(adapter, source("a", "b"))
    assert summary.record.status is RunStatus.PARTIAL
    (error,) = summary.record.errors
    assert (error.code, error.query_index, error.http_status, error.attempts) == (
        "invalid_response",
        0,
        200,
        1,
    )
    assert error.message == "results is not a list"


async def test_unexpected_adapter_errors_are_sanitized_and_recorded() -> None:
    stream = io.StringIO()
    configure_logging("INFO", stream)
    adapter = ScriptedAdapter({"a": [KeyError("private-value")], "b": [page("2")]})
    summary, _, _ = await run(adapter, source("a", "b"))
    assert summary.record.errors[0].code == "internal_error"
    assert "private-value" not in summary.record.errors[0].message
    assert "private-value" not in stream.getvalue()
    assert summary.record.status is RunStatus.PARTIAL


async def test_a_persistence_failure_stops_the_run_and_is_never_a_success() -> None:
    stream = io.StringIO()
    configure_logging("INFO", stream)
    adapter = ScriptedAdapter({"a": [page("1")], "b": [page("2")]})
    summary, _, sender = await run(adapter, source("a", "b"), store=FakeStore(fail_store=True))
    assert summary.record.status is RunStatus.FAILED
    assert [e.code for e in summary.record.errors] == ["persistence_error"]
    assert len(sender.requests) == 1
    assert "private-value" not in stream.getvalue()


async def test_logs_identify_the_run() -> None:
    stream = io.StringIO()
    configure_logging("INFO", stream)
    summary, _, _ = await run(ScriptedAdapter({"a": [page("1")]}), source("a"))
    entries = [json.loads(line) for line in stream.getvalue().splitlines()]
    events = {e["event"]: e for e in entries if "event" in e}
    assert {"run_started", "page_stored", "run_finished"} <= set(events)
    assert all(e["run_id"] == str(summary.record.run_id) for e in events.values())
    assert events["run_finished"]["requests"] == 1


async def test_a_locked_source_creates_no_run_and_sends_nothing() -> None:
    store, sender = FakeStore(locked=True), FakeSender({})
    with pytest.raises(RunInProgress):
        await run(ScriptedAdapter({"a": []}), source("a"), store=store, sender=sender)
    assert store.records == {}
    assert sender.requests == []


async def test_abandoned_runs_are_reported() -> None:
    summary, _, _ = await run(
        ScriptedAdapter({"a": [page()]}), source("a"), store=FakeStore(abandoned=1)
    )
    assert summary.abandoned_closed == 1


async def test_the_status_follows_the_domain_rule() -> None:
    summary, _, _ = await run(ScriptedAdapter({"a": [page("1", rejected=1)]}), source("a"))
    counts = summary.record.counts
    assert summary.record.status is final_status(
        valid=counts.valid, rejected=counts.rejected, failures=counts.failures
    )


async def test_measured_metrics_are_persisted_with_the_run() -> None:
    ticks = iter([10.0, 20.0, 20.25, 30.0])  # run start, storing a page, storing end, run end
    store, sender = FakeStore(), FakeSender({})
    engine = DiscoveryEngine(
        runs=store,
        catalog=store,
        sender_factory=lambda _: sender,
        clock=lambda: NOW,
        timer=lambda: next(ticks),
    )
    summary = await engine.discover(source("a"), ScriptedAdapter({"a": [page("1")]}))
    assert summary.record.metrics == RunMetrics(
        requests=1, duration_ms=20000, persistence_ms=250, rejection_reasons={}
    )
