"""Catalog and run persistence against PostgreSQL (AC-03 to AC-09, AC-26, AC-36).

All sources and datasets are synthetic.
"""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from fdh.controlplane.runs import (
    ObservedPage,
    RunCounts,
    RunError,
    RunInProgress,
    RunMetrics,
)
from fdh.controlplane.sources import plan_source_sync
from fdh.domain.datasets import (
    AccessLocator,
    DatasetDates,
    DeclaredLicense,
    DiscoveredDataset,
)
from fdh.domain.permissions import Permission
from fdh.domain.sources import DiscoveryQuery, PublicationDecision, SourceDefinition
from fdh.domain.status import RunStatus
from fdh.persistence.catalog import SqlCatalogRepository
from fdh.persistence.runs import SqlRunRepository
from fdh.persistence.session import create_sessions
from fdh.persistence.sources import SqlSourceRepository

T0 = datetime(2026, 1, 1, tzinfo=UTC)
QUERIES = (DiscoveryQuery("budget"), DiscoveryQuery("finance", {"kind": "x"}))
INTERRUPTED = RunError("interrupted", "synthetic interruption")

FULL = DiscoveredDataset(
    external_id="full-1",
    title="Synthetic complete",
    description="Synthetic description",
    publisher="Synthetic Publisher",
    official_url="https://data.example.org/d/full-1",
    categories=("Hacienda", "HACIENDA"),
    topics=("Economía",),
    tags=("a", "b"),
    data_sources=("Synthetic Organisation",),
    licenses=(DeclaredLicense("L1", "https://example.org/l1", "note"), DeclaredLicense("L2")),
    citation_requirement="Cite it",
    dates=DatasetDates(
        created_at=T0,
        published_at=T0 + timedelta(days=1),
        metadata_updated_at=T0 + timedelta(days=2),
        data_updated_at=T0 + timedelta(days=3),
        updated_at=T0 + timedelta(days=4),
    ),
    locators=(
        AccessLocator("web", "https://data.example.org/d/full-1", "permalink"),
        AccessLocator("api", "http://data.example.org/insecure", "link"),
    ),
)


def minimal(external_id: str, title: str = "Synthetic") -> DiscoveredDataset:
    return DiscoveredDataset(external_id, title)


class Store:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.catalog = SqlCatalogRepository(create_sessions(engine))
        self.runs = SqlRunRepository(engine)

    async def register(self, *source_ids: str) -> None:
        definitions = [
            SourceDefinition(
                source_id=source_id,
                provider="Synthetic Provider",
                platform="socrata",
                base_url="https://api.example.org",
                allowed_hosts=("api.example.org",),
                official_url="https://www.example.org",
                verified_at=date(2026, 1, 2),
                publication=PublicationDecision(
                    Permission.ALLOWED, "maintainer", date(2026, 1, 1), "https://example.org/e"
                ),
            )
            for source_id in source_ids
        ]
        await SqlSourceRepository(create_sessions(self.engine)).synchronise(
            lambda registered: plan_source_sync(definitions, registered, today=date(2026, 1, 3))
        )

    async def start(self, source_id: str = "alpha") -> UUID:
        return await self.runs.start(source_id, {"queries": []}, QUERIES)

    async def page(
        self,
        run_id: UUID,
        *datasets: DiscoveredDataset,
        query: int = 0,
        source_id: str = "alpha",
        rejected: int = 0,
        total: int | None = None,
        at: datetime = T0,
    ) -> None:
        await self.catalog.store_page(
            ObservedPage(
                run_id=run_id,
                source_id=source_id,
                query_index=query,
                source_url=f"https://api.example.org?q={query}",
                request_summary={"method": "GET", "params": {"q": str(query)}},
                observed_at=at,
                datasets=datasets,
                rejected=rejected,
                total_declared=total,
            )
        )

    async def run(
        self, *datasets: DiscoveredDataset, at: datetime = T0, source_id: str = "alpha"
    ) -> UUID:
        run_id = await self.start(source_id)
        await self.page(run_id, *datasets, at=at, source_id=source_id)
        await self.runs.finish(run_id, RunStatus.SUCCEEDED, RunMetrics())
        return run_id

    async def rows(self, statement: str, **values: Any) -> list[tuple[Any, ...]]:
        async with self.engine.connect() as connection:
            result = await connection.execute(text(statement), values)
            return [tuple(row) for row in result]

    async def execute(self, statement: str) -> None:
        async with self.engine.begin() as connection:
            await connection.execute(text(statement))


@pytest.fixture
async def store(engine: AsyncEngine) -> Store:
    created = Store(engine)
    await created.register("alpha", "beta")
    return created


async def counts(store: Store, run_id: UUID) -> RunCounts:
    return await store.runs.counts(run_id)


async def test_a_dataset_found_by_two_queries_is_one_record_with_both(store: Store) -> None:
    run_id = await store.start()
    await store.page(run_id, minimal("x"), query=0)
    await store.page(run_id, minimal("x"), query=1)
    assert await store.rows("SELECT count(*) FROM datasets") == [(1,)]
    assert await store.rows(
        "SELECT query_index, source_url, request_summary->'params'->>'q', run_id "
        "FROM dataset_observations ORDER BY query_index"
    ) == [
        (0, "https://api.example.org?q=0", "0", run_id),
        (1, "https://api.example.org?q=1", "1", run_id),
    ]
    assert await counts(store, run_id) == RunCounts(pages_processed=2, received=2, created=1)


async def test_repetitions_inside_a_page_are_counted_once(store: Store) -> None:
    run_id = await store.start()
    await store.page(run_id, minimal("x", "first"), minimal("x", "second"), minimal("y"))
    assert await store.rows("SELECT external_id, title FROM datasets ORDER BY 1") == [
        ("x", "second"),
        ("y", "Synthetic"),
    ]
    assert await store.rows("SELECT count(*) FROM dataset_observations") == [(2,)]
    assert await counts(store, run_id) == RunCounts(pages_processed=1, received=3, created=2)


async def test_repeating_a_run_updates_without_duplicating(store: Store) -> None:
    first = await store.run(minimal("same"), minimal("changed", "before"))
    later = T0 + timedelta(hours=1)
    second = await store.run(minimal("same"), minimal("changed", "after"), at=later)
    assert await store.rows(
        "SELECT external_id, title, first_seen_at, last_seen_at, first_seen_run_id, "
        "last_seen_run_id FROM datasets ORDER BY 1"
    ) == [
        ("changed", "after", T0, later, first, second),
        ("same", "Synthetic", T0, later, first, second),
    ]
    assert await counts(store, second) == RunCounts(
        pages_processed=1, received=2, updated=1, unchanged=1
    )
    assert await store.rows("SELECT count(*) FROM runs") == [(2,)]
    assert await store.rows("SELECT count(*) FROM dataset_observations") == [(4,)]


async def test_an_absent_dataset_is_kept_with_its_last_observation(store: Store) -> None:
    first = await store.run(minimal("stays"), minimal("disappears"))
    later = T0 + timedelta(days=1)
    await store.run(minimal("stays"), at=later)
    assert await store.rows(
        "SELECT external_id, last_seen_at, last_seen_run_id = :first FROM datasets ORDER BY 1",
        first=first,
    ) == [("disappears", T0, True), ("stays", later, False)]


async def test_the_same_identifier_in_two_sources_is_two_records(store: Store) -> None:
    await store.run(minimal("shared", "from alpha"))
    await store.run(minimal("shared", "from beta"), source_id="beta")
    assert await store.rows("SELECT source_id, title FROM datasets ORDER BY 1") == [
        ("alpha", "from alpha"),
        ("beta", "from beta"),
    ]


async def test_the_database_refuses_a_duplicate(store: Store) -> None:
    await store.run(minimal("x"))
    with pytest.raises(IntegrityError):
        await store.execute(
            "INSERT INTO datasets (id, source_id, external_id, title, first_seen_run_id, "
            "last_seen_run_id, metadata_hash) SELECT gen_random_uuid(), source_id, external_id, "
            "title, first_seen_run_id, last_seen_run_id, metadata_hash FROM datasets"
        )


async def test_all_metadata_is_stored_and_nothing_is_permitted(store: Store) -> None:
    await store.run(FULL)
    (row,) = await store.rows(
        "SELECT title, description, publisher, official_url, categories, topics, tags, "
        "category_keys, data_sources, licenses, citation_requirement, created_at_source, "
        "published_at_source, metadata_updated_at_source, data_updated_at_source, "
        "updated_at_source, review_status::text, extraction_permission::text, "
        "redistribution_permission::text, access_conditions, redistribution_conditions "
        "FROM datasets"
    )
    assert row == (
        "Synthetic complete",
        "Synthetic description",
        "Synthetic Publisher",
        "https://data.example.org/d/full-1",
        ["Hacienda", "HACIENDA"],
        ["Economía"],
        ["a", "b"],
        ["hacienda", "economía"],
        ["Synthetic Organisation"],
        [
            {"name": "L1", "url": "https://example.org/l1", "note": "note"},
            {"name": "L2", "url": None, "note": None},
        ],
        "Cite it",
        *(T0 + timedelta(days=n) for n in range(5)),
        "pending",
        "undetermined",
        "undetermined",
        None,
        None,
    )


async def test_unknown_values_stay_unknown(store: Store) -> None:
    await store.run(minimal("x"))
    assert await store.rows(
        "SELECT description, publisher, official_url, categories, licenses, created_at_source "
        "FROM datasets"
    ) == [(None, None, None, [], [], None)]


LOCATORS = "SELECT kind, url, source_field, status::text FROM access_locators ORDER BY kind"


async def test_locators_are_replaced_and_validated_again(store: Store) -> None:
    repeated = replace(FULL, locators=(*FULL.locators, FULL.locators[0]))
    await store.run(repeated)
    assert await store.rows(LOCATORS) == [
        ("api", "http://data.example.org/insecure", "link", "invalid"),
        ("web", "https://data.example.org/d/full-1", "permalink", "unverified"),
    ]
    corrected = replace(
        FULL, locators=(AccessLocator("api", "https://data.example.org/secure", "link"),)
    )
    second = await store.run(corrected)
    assert await store.rows(LOCATORS) == [
        ("api", "https://data.example.org/secure", "link", "unverified")
    ]
    assert (await counts(store, second)).updated == 1


async def test_very_long_locators_are_accepted(store: Store) -> None:
    url = "https://data.example.org/" + "x" * 20_000
    await store.run(replace(minimal("x"), locators=(AccessLocator("web", url, "link"),)))
    assert await store.rows("SELECT length(url) FROM access_locators") == [(len(url),)]


async def test_rediscovery_never_changes_what_a_person_recorded(store: Store) -> None:
    await store.run(minimal("x", "before"))
    await store.execute(
        "UPDATE datasets SET review_status = 'restricted', extraction_permission = 'denied', "
        "redistribution_permission = 'allowed', access_conditions = 'recorded access', "
        "redistribution_conditions = 'recorded redistribution'"
    )
    await store.run(replace(FULL, external_id="x", title="after"))
    assert await store.rows(
        "SELECT title, review_status::text, extraction_permission::text, "
        "redistribution_permission::text, access_conditions, redistribution_conditions "
        "FROM datasets"
    ) == [
        ("after", "restricted", "denied", "allowed", "recorded access", "recorded redistribution")
    ]


async def test_the_source_records_its_url_and_verification_date(store: Store) -> None:
    assert await store.rows(
        "SELECT official_url, verified_at FROM sources WHERE source_id = 'alpha'"
    ) == [("https://www.example.org", date(2026, 1, 2))]


async def test_a_page_is_stored_entirely_or_not_at_all(store: Store) -> None:
    run_id = await store.start()
    broken = DiscoveredDataset("broken", "Synthetic", tags=("null \x00 byte",))
    with pytest.raises(DBAPIError):
        await store.page(run_id, minimal("valid"), broken, rejected=1)
    assert await store.rows("SELECT count(*) FROM datasets") == [(0,)]
    assert await counts(store, run_id) == RunCounts()


async def test_a_page_with_only_rejections_is_counted(store: Store) -> None:
    run_id = await store.start()
    await store.page(run_id, rejected=3, total=3)
    assert await counts(store, run_id) == RunCounts(pages_processed=1, received=3, rejected=3)


async def test_a_failed_run_keeps_previous_data(store: Store) -> None:
    await store.run(minimal("x", "kept"))
    run_id = await store.start()
    await store.runs.record_failure(run_id, RunError("timeout", "synthetic", 0, None, 4))
    await store.runs.finish(run_id, RunStatus.FAILED, RunMetrics())
    record = await store.runs.get(run_id)
    assert (record.status, record.counts.failures) == (RunStatus.FAILED, 1)
    assert record.errors == (RunError("timeout", "synthetic", 0, None, 4),)
    assert record.finished_at is not None
    assert await store.rows("SELECT title FROM datasets") == [("kept",)]


async def test_a_run_records_its_queries_totals_and_truncation(store: Store) -> None:
    run_id = await store.start()
    assert (await store.runs.get(run_id)).status is RunStatus.RUNNING
    await store.page(run_id, minimal("x"), total=40)
    await store.page(run_id, minimal("y"), total=None)
    await store.runs.mark_truncated(run_id, 0)
    first, second = (await store.runs.get(run_id)).queries
    assert (first.term, first.pages_processed, first.total_declared, first.truncated) == (
        "budget",
        2,
        40,
        True,
    )
    assert (second.term, second.filters, second.pages_processed, second.truncated) == (
        "finance",
        {"kind": "x"},
        0,
        False,
    )
    assert second.total_declared is None
    assert await store.rows("SELECT parameters FROM runs") == [({"queries": []},)]


async def test_a_finished_run_cannot_be_finished_again(store: Store) -> None:
    run_id = await store.run(minimal("x"))
    with pytest.raises(LookupError):
        await store.runs.finish(run_id, RunStatus.FAILED, RunMetrics())


async def test_one_run_per_source_at_a_time(store: Store) -> None:
    other = SqlRunRepository(store.engine)
    async with store.runs.source_lock("alpha"):
        with pytest.raises(RunInProgress):
            async with other.source_lock("alpha"):
                pytest.fail("the lock was taken twice")
        async with other.source_lock("beta"):
            pass
    async with other.source_lock("alpha"):
        pass


async def test_the_lock_is_released_after_an_error(store: Store) -> None:
    with pytest.raises(ValueError, match="synthetic"):
        async with store.runs.source_lock("alpha"):
            raise ValueError("synthetic")
    async with SqlRunRepository(store.engine).source_lock("alpha"):
        pass


async def test_abandoned_runs_are_closed_with_an_interruption(store: Store) -> None:
    empty = await store.start()
    with_data = await store.start()
    await store.page(with_data, minimal("x"))
    other_source = await store.start("beta")
    finished = await store.run(minimal("y"))
    assert await store.runs.close_abandoned("alpha", INTERRUPTED) == 2
    statuses = {}
    for run_id in (empty, with_data, other_source, finished):
        record = await store.runs.get(run_id)
        statuses[run_id] = (record.status, [e.code for e in record.errors])
    assert statuses == {
        empty: (RunStatus.FAILED, ["interrupted"]),
        with_data: (RunStatus.PARTIAL, ["interrupted"]),
        other_source: (RunStatus.RUNNING, []),
        finished: (RunStatus.SUCCEEDED, []),
    }


def identifiers(records: Sequence[Any]) -> list[UUID]:
    return [record.run_id for record in records]


async def test_recent_runs_come_first_and_are_limited(store: Store) -> None:
    first = await store.start()
    second = await store.start("beta")
    third = await store.start()
    assert identifiers(await store.runs.recent(None, 10)) == [third, second, first]
    assert identifiers(await store.runs.recent("alpha", 10)) == [third, first]
    assert identifiers(await store.runs.recent(None, 1)) == [third]


async def test_metrics_are_stored_when_a_run_finishes(store: Store) -> None:
    run_id = await store.start()
    assert (await store.runs.get(run_id)).metrics == RunMetrics()
    metrics = RunMetrics(4, 1620, 190, {"missing_title": 2})
    await store.runs.finish(run_id, RunStatus.PARTIAL, metrics)
    assert (await store.runs.get(run_id)).metrics == metrics
    empty = await store.start()
    await store.runs.finish(empty, RunStatus.SUCCEEDED, RunMetrics(1, 0, 0, {}))
    assert (await store.runs.get(empty)).metrics == RunMetrics(1, 0, 0, {})


async def test_an_interrupted_run_has_unknown_metrics(store: Store) -> None:
    run_id = await store.start()
    await store.runs.close_abandoned("alpha", INTERRUPTED)
    assert (await store.runs.get(run_id)).metrics == RunMetrics()
    assert await store.rows("SELECT requests, rejection_reasons FROM runs") == [(None, None)]
