"""`fdh discover` and `fdh runs list`: composition of the discovery modules and their output."""

import json
import logging
import sys
from collections.abc import Sequence

import httpx

from fdh.cli.database import database_engine
from fdh.controlplane.runs import RunInProgress, RunRecord
from fdh.dataplane.connectors.registry import AdapterRegistry
from fdh.dataplane.discovery.engine import DiscoveryEngine, RunSummary
from fdh.dataplane.discovery.http import HttpExecutor
from fdh.domain.sources import SourceDefinition
from fdh.domain.status import RunStatus
from fdh.observability.logging import run_context
from fdh.persistence.catalog import SqlCatalogRepository
from fdh.persistence.runs import SqlRunRepository
from fdh.persistence.session import create_sessions
from fdh.settings.env import Settings

OK, RUNTIME_ERROR = 0, 1
RUN_PARTIAL, RUN_FAILED, RUN_IN_PROGRESS = 3, 4, 5
# With several sources, the exit code reports the most severe outcome.
_SEVERITY = (RUNTIME_ERROR, RUN_FAILED, RUN_IN_PROGRESS, RUN_PARTIAL, OK)
_EXIT_CODES = {RunStatus.SUCCEEDED: OK, RunStatus.PARTIAL: RUN_PARTIAL}
USER_AGENT = "fdh-discovery"  # generic on purpose: no contact or personal data
log = logging.getLogger("fdh.cli")


def _optional(value: object) -> str:
    return "-" if value is None else str(value)


def _quoted(term: str | None) -> str:
    return "-" if term is None else json.dumps(term, ensure_ascii=False)


def _counts(record: RunRecord) -> str:
    c = record.counts
    return (
        f"pages={c.pages_processed} received={c.received} unique={c.valid} "
        f"created={c.created} updated={c.updated} unchanged={c.unchanged} "
        f"rejected={c.rejected} failures={c.failures}"
    )


def _errors(record: RunRecord) -> list[str]:
    return [
        f"  error: code={e.code} query={_optional(e.query_index)} "
        f"http_status={_optional(e.http_status)} attempts={_optional(e.attempts)} {e.message}"
        for e in record.errors
    ]


def format_summary(summary: RunSummary) -> str:
    record, metrics = summary.record, summary.metrics
    lines = [
        f"{record.source_id}: run {record.run_id} {record.status.value}",
        f"  requests={metrics.requests} {_counts(record)}",
        f"  duration={metrics.duration_s:.2f}s persistence={metrics.persistence_s:.2f}s",
    ]
    lines += [
        f"  query {q.query_index}: term={_quoted(q.term)} pages={q.pages_processed} "
        f"total_declared={_optional(q.total_declared)} truncated={'yes' if q.truncated else 'no'}"
        for q in record.queries
    ]
    if summary.rejection_reasons:
        reasons = " ".join(f"{k}={v}" for k, v in sorted(summary.rejection_reasons.items()))
        lines.append(f"  rejected: {reasons}")
    if summary.abandoned_closed:
        lines.append(f"  closed {summary.abandoned_closed} interrupted run(s)")
    return "\n".join(lines + _errors(record))


def format_run(record: RunRecord) -> str:
    finished = record.finished_at
    duration = "-" if finished is None else f"{(finished - record.started_at).total_seconds():.2f}s"
    truncated = sum(query.truncated for query in record.queries)
    line = (
        f"{record.started_at:%Y-%m-%dT%H:%M:%SZ} {record.run_id} {record.source_id} "
        f"{record.status.value} {_counts(record)} truncated={truncated} duration={duration}"
    )
    return "\n".join([line, *_errors(record)])


async def discover(
    settings: Settings,
    sources: Sequence[SourceDefinition],
    registry: AdapterRegistry,
    transport: httpx.AsyncBaseTransport | None = None,
) -> int:
    """Discover each source in turn. One source never prevents the following ones."""
    engine = database_engine(settings)
    codes = [OK]
    try:
        # The executor owns deadlines and redirects. The environment cannot add proxies
        # or credentials to the requests.
        async with httpx.AsyncClient(
            transport=transport,
            timeout=None,  # noqa: S113
            trust_env=False,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            discovery = DiscoveryEngine(
                runs=SqlRunRepository(engine),
                catalog=SqlCatalogRepository(create_sessions(engine)),
                sender_factory=lambda source: HttpExecutor(
                    client, allowed_hosts=source.allowed_hosts, limits=source.limits
                ),
                run_scope=run_context,
            )
            for source in sources:
                try:
                    summary = await discovery.discover(source, registry.create(source.platform))
                except RunInProgress:
                    print(
                        f"error: a run is already in progress for {source.source_id}",
                        file=sys.stderr,
                    )
                    codes.append(RUN_IN_PROGRESS)
                except Exception as error:
                    log.error(
                        "discovery failed",
                        extra={
                            "event": "discovery_failed",
                            "source_id": source.source_id,
                            "error_type": type(error).__name__,
                        },
                    )
                    print(
                        f"error: discovery of {source.source_id} failed; see the log",
                        file=sys.stderr,
                    )
                    codes.append(RUNTIME_ERROR)
                else:
                    print(format_summary(summary))
                    codes.append(_EXIT_CODES.get(summary.record.status, RUN_FAILED))
    finally:
        await engine.dispose()
    return min(codes, key=_SEVERITY.index)


async def list_runs(settings: Settings, source_id: str | None, limit: int) -> int:
    engine = database_engine(settings)
    try:
        records = await SqlRunRepository(engine).recent(source_id, limit)
    finally:
        await engine.dispose()
    for record in records:
        print(format_run(record))
    if not records:
        print("no runs")
    return OK
