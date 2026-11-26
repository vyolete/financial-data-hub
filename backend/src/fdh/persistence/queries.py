"""Bounded, read-only PostgreSQL catalog queries."""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import TypeVarTuple, cast
from uuid import UUID

from sqlalchemy import Select, Text, and_, func, literal, or_, select, type_coerce
from sqlalchemy.exc import OperationalError, TimeoutError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from fdh.controlplane.catalog import Record, ResourceNotFound, StorageUnavailable
from fdh.domain.permissions import Permission, ReviewStatus
from fdh.persistence.models import (
    AccessLocatorRow,
    Dataset,
    DatasetObservation,
    Run,
    RunQuery,
    Source,
)
from fdh.persistence.session import create_sessions

Columns = TypeVarTuple("Columns")
VISIBLE = and_(
    Source.metadata_publication == Permission.ALLOWED,
    Dataset.review_status != ReviewStatus.RESTRICTED,
)


def _contains(column: object, query: str) -> ColumnElement[bool]:
    # Escape after unaccent, which can itself turn compatibility forms into wildcards.
    escaped = func.replace(
        func.replace(func.replace(func.unaccent(literal(query)), "\\", "\\\\"), "%", "\\%"),
        "_",
        "\\_",
    )
    return func.unaccent(column).ilike(literal("%") + escaped + literal("%"), escape="\\")


def _fields(row: object, names: str) -> Record:
    return {name: getattr(row, name) for name in names.split()}


def _summary(dataset: Dataset, source: Source) -> Record:
    return {
        **_fields(
            dataset,
            "id source_id external_id title description publisher categories topics "
            "review_status licenses last_seen_at",
        ),
        **_fields(source, "provider platform"),
        "attribution": {
            "text": source.attribution_text,
            "data_sources": dataset.data_sources,
            "data_updated_at": dataset.data_updated_at_source,
            "citation_requirement": dataset.citation_requirement,
        },
    }


def _run(run: Run, truncated: bool) -> Record:
    return {
        **_fields(
            run,
            "id source_id status started_at finished_at pages_processed received "
            "created updated unchanged rejected failures requests duration_ms persistence_ms",
        ),
        "truncated": truncated,
    }


class SqlQueryRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = create_sessions(
            engine.execution_options(
                isolation_level="REPEATABLE READ",
                postgresql_readonly=True,
            )
        )

    @asynccontextmanager
    async def _read(self) -> AsyncIterator[AsyncSession]:
        try:
            async with self._sessions() as session, session.begin():
                yield session
        except (OperationalError, TimeoutError, OSError) as error:
            raise StorageUnavailable from error

    async def _page(
        self,
        session: AsyncSession,
        statement: Select[*Columns],
        page: int,
        size: int,
    ) -> tuple[Record, Sequence[tuple[*Columns]]]:
        total = await session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        )
        rows = await session.execute(statement.offset((page - 1) * size).limit(size))
        return {"page": page, "page_size": size, "total": total}, cast(
            "Sequence[tuple[*Columns]]", rows.all()
        )

    async def datasets(self, page: int, size: int, q: str, provider: str, category: str) -> Record:
        statement = select(Dataset, Source).join(Source).where(VISIBLE)
        if q:
            statement = statement.where(
                or_(_contains(Dataset.title, q), _contains(Dataset.description, q))
            )
        if provider:
            statement = statement.where(Source.provider == provider)
        if category:
            statement = statement.where(Dataset.category_keys.contains([category.casefold()]))
        async with self._read() as session:
            meta, rows = await self._page(
                session, statement.order_by(Dataset.title, Dataset.id), page, size
            )
            return {**meta, "items": [_summary(dataset, source) for dataset, source in rows]}

    async def _dataset(self, session: AsyncSession, id: UUID) -> tuple[Dataset, Source]:
        row = (
            await session.execute(
                select(Dataset, Source).join(Source).where(VISIBLE, Dataset.id == id)
            )
        ).one_or_none()
        if row is None:
            raise ResourceNotFound
        dataset, source = row
        return dataset, source

    async def _observations(self, session: AsyncSession, id: UUID, page: int, size: int) -> Record:
        obs = DatasetObservation
        statement = (
            select(obs, RunQuery.term)
            .outerjoin(
                RunQuery,
                and_(RunQuery.run_id == obs.run_id, RunQuery.query_index == obs.query_index),
            )
            .where(obs.dataset_id == id)
            .order_by(obs.observed_at.desc(), obs.id.desc())
        )
        meta, rows = await self._page(session, statement, page, size)
        return {
            **meta,
            "items": [
                {**_fields(row, "run_id source_url observed_at"), "query_term": term}
                for row, term in rows
            ],
        }

    async def dataset(self, id: UUID) -> Record:
        async with self._read() as session:
            dataset, source = await self._dataset(session, id)
            locators = await session.scalars(
                select(AccessLocatorRow)
                .where(AccessLocatorRow.dataset_id == id)
                .order_by(
                    AccessLocatorRow.kind, AccessLocatorRow.url, AccessLocatorRow.source_field
                )
            )
            provenance = await self._observations(session, id, 1, 20)
            return {
                **_summary(dataset, source),
                **_fields(
                    dataset,
                    "tags official_url access_conditions redistribution_conditions "
                    "extraction_permission redistribution_permission first_seen_at",
                ),
                **{
                    name: getattr(dataset, f"{name}_source")
                    for name in (
                        "created_at",
                        "published_at",
                        "metadata_updated_at",
                        "data_updated_at",
                        "updated_at",
                    )
                },
                "source": _fields(
                    source,
                    "official_url verified_at access_conditions redistribution_conditions "
                    "license_name license_url terms_url terms_checked_on",
                ),
                "locators": [
                    _fields(locator, "kind url source_field status") for locator in locators
                ],
                "provenance": {"items": provenance["items"], "total": provenance["total"]},
            }

    async def provenance(self, id: UUID, page: int, size: int) -> Record:
        async with self._read() as session:
            await self._dataset(session, id)
            return await self._observations(session, id, page, size)

    async def providers(self, page: int, size: int) -> Record:
        statement = (
            select(Source.provider)
            .select_from(Dataset)
            .join(Source)
            .where(VISIBLE)
            .distinct()
            .order_by(Source.provider)
        )
        async with self._read() as session:
            meta, rows = await self._page(session, statement, page, size)
            return {**meta, "items": [value for (value,) in rows]}

    async def categories(self, page: int, size: int, q: str) -> Record:
        originals = (
            select(func.unnest(Dataset.categories.concat(Dataset.topics)).label("value"))
            .join(Source)
            .where(VISIBLE)
            .subquery()
        )
        value = originals.c.value
        statement = (
            select(type_coerce(func.min(value), Text).label("name"))
            .group_by(func.casefold(value))
            .order_by("name")
        )
        if q:
            statement = statement.where(_contains(value, q))
        async with self._read() as session:
            meta, rows = await self._page(session, statement, page, size)
            return {**meta, "items": [item for (item,) in rows]}

    async def runs(self, page: int, size: int, source_id: str) -> Record:
        truncated = (
            select(RunQuery.run_id).where(RunQuery.run_id == Run.id, RunQuery.truncated).exists()
        )
        statement = select(Run, truncated).order_by(Run.started_at.desc(), Run.id.desc())
        if source_id:
            statement = statement.where(Run.source_id == source_id)
        async with self._read() as session:
            meta, rows = await self._page(session, statement, page, size)
            return {**meta, "items": [_run(run, flag) for run, flag in rows]}

    async def run(self, id: UUID) -> Record:
        async with self._read() as session:
            run = await session.get(Run, id)
            if run is None:
                raise ResourceNotFound
            queries = list(
                await session.scalars(
                    select(RunQuery).where(RunQuery.run_id == id).order_by(RunQuery.query_index)
                )
            )
            return {
                **_run(run, any(query.truncated for query in queries)),
                "queries": [
                    _fields(query, "query_index term pages_processed total_declared truncated")
                    for query in queries
                ],
                "errors": run.errors,
                "rejection_reasons": run.rejection_reasons,
            }
