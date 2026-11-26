"""Runs, their queries and the per-source lock, in PostgreSQL."""

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from fdh.controlplane.runs import (
    ObservedPage,
    QueryRecord,
    RunCounts,
    RunError,
    RunInProgress,
    RunRecord,
)
from fdh.domain.sources import DiscoveryQuery
from fdh.domain.status import RunStatus, final_status
from fdh.persistence.models import Run, RunQuery
from fdh.persistence.session import create_sessions

_LOCK_PREFIX = "fdh.discover:"


def _counts(row: Run) -> RunCounts:
    return RunCounts(
        pages_processed=row.pages_processed,
        received=row.received,
        created=row.created,
        updated=row.updated,
        unchanged=row.unchanged,
        rejected=row.rejected,
        failures=row.failures,
    )


def _append(row: Run, error: RunError) -> None:
    row.failures += 1
    row.errors = [*row.errors, asdict(error)]


async def add_page(
    session: AsyncSession, page: ObservedPage, *, created: int, updated: int, unchanged: int
) -> None:
    """Add a page to the counts of its run, inside the transaction that stores the page."""
    run = await session.execute(
        update(Run)
        .where(Run.id == page.run_id, Run.status == RunStatus.RUNNING)
        .values(
            pages_processed=Run.pages_processed + 1,
            received=Run.received + len(page.datasets) + page.rejected,
            created=Run.created + created,
            updated=Run.updated + updated,
            unchanged=Run.unchanged + unchanged,
            rejected=Run.rejected + page.rejected,
        )
        .returning(Run.id)
    )
    query = await session.execute(
        update(RunQuery)
        .where(RunQuery.run_id == page.run_id, RunQuery.query_index == page.query_index)
        .values(
            pages_processed=RunQuery.pages_processed + 1,
            total_declared=func.coalesce(page.total_declared, RunQuery.total_declared),
        )
        .returning(RunQuery.run_id)
    )
    if run.first() is None or query.first() is None:
        raise LookupError("the page does not belong to a running query")


class SqlRunRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = create_sessions(engine)

    @asynccontextmanager
    async def source_lock(self, source_id: str) -> AsyncIterator[None]:
        """A PostgreSQL advisory lock held by its own connection for the whole run."""
        key = func.hashtext(_LOCK_PREFIX + source_id)
        async with self._engine.connect() as connection:
            await connection.execution_options(isolation_level="AUTOCOMMIT")
            if not await connection.scalar(select(func.pg_try_advisory_lock(key))):
                raise RunInProgress(source_id)
            try:
                yield
            finally:
                try:
                    await connection.execute(select(func.pg_advisory_unlock(key)))
                except Exception:
                    # Discarding the connection releases the lock and keeps the first error.
                    await connection.invalidate()

    async def close_abandoned(self, source_id: str, error: RunError) -> int:
        async with self._sessions() as session, session.begin():
            rows = (
                await session.scalars(
                    select(Run)
                    .where(Run.source_id == source_id, Run.status == RunStatus.RUNNING)
                    .with_for_update()
                )
            ).all()
            for row in rows:
                _append(row, error)
                counts = _counts(row)
                row.status = final_status(
                    valid=counts.valid, rejected=counts.rejected, failures=counts.failures
                )
                row.finished_at = func.now()
        return len(rows)

    async def start(
        self, source_id: str, parameters: Mapping[str, Any], queries: Sequence[DiscoveryQuery]
    ) -> UUID:
        async with self._sessions() as session, session.begin():
            row = Run(source_id=source_id, status=RunStatus.RUNNING, parameters=dict(parameters))
            session.add(row)
            await session.flush()
            session.add_all(
                RunQuery(run_id=row.id, query_index=i, term=q.term, filters=dict(q.filters))
                for i, q in enumerate(queries)
            )
        return row.id

    async def record_failure(self, run_id: UUID, error: RunError) -> None:
        async with self._sessions() as session, session.begin():
            row = await session.get(Run, run_id, with_for_update=True)
            if row is None or row.status is not RunStatus.RUNNING:
                raise LookupError("the run is not running")
            _append(row, error)

    async def mark_truncated(self, run_id: UUID, query_index: int) -> None:
        async with self._sessions() as session, session.begin():
            await session.execute(
                update(RunQuery)
                .where(RunQuery.run_id == run_id, RunQuery.query_index == query_index)
                .values(truncated=True)
            )

    async def counts(self, run_id: UUID) -> RunCounts:
        async with self._sessions() as session:
            return _counts(await session.get_one(Run, run_id))

    async def finish(self, run_id: UUID, status: RunStatus) -> None:
        async with self._sessions() as session, session.begin():
            finished = await session.execute(
                update(Run)
                .where(Run.id == run_id, Run.status == RunStatus.RUNNING)
                .values(status=status, finished_at=func.clock_timestamp())
                .returning(Run.id)
            )
            if finished.first() is None:
                raise LookupError("the run is not running")

    async def get(self, run_id: UUID) -> RunRecord:
        async with self._sessions() as session:
            (record,) = await self._records(session, [await session.get_one(Run, run_id)])
        return record

    async def recent(self, source_id: str | None, limit: int) -> Sequence[RunRecord]:
        statement = select(Run).order_by(Run.started_at.desc(), Run.id).limit(limit)
        if source_id is not None:
            statement = statement.where(Run.source_id == source_id)
        async with self._sessions() as session:
            return await self._records(session, (await session.scalars(statement)).all())

    async def _records(self, session: AsyncSession, rows: Sequence[Run]) -> list[RunRecord]:
        queries: dict[UUID, list[QueryRecord]] = {row.id: [] for row in rows}
        if queries:
            for query in await session.scalars(
                select(RunQuery).where(RunQuery.run_id.in_(queries)).order_by(RunQuery.query_index)
            ):
                queries[query.run_id].append(
                    QueryRecord(
                        query.query_index,
                        query.term,
                        query.filters,
                        query.pages_processed,
                        query.total_declared,
                        query.truncated,
                    )
                )
        return [
            RunRecord(
                row.id,
                row.source_id,
                row.status,
                row.started_at,
                row.finished_at,
                _counts(row),
                tuple(RunError(**error) for error in row.errors),
                tuple(queries[row.id]),
            )
            for row in rows
        ]
