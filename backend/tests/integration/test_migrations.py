"""Schema and constraints on real PostgreSQL. All rows are synthetic."""

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from tests.integration.conftest import alembic

SOURCE = """INSERT INTO sources (source_id, provider, platform, official_url, verified_at)
            VALUES (:id, 'P', 'socrata', 'https://example.org', DATE '2026-01-01')"""
RUN = """INSERT INTO runs (id, source_id, status)
         VALUES (gen_random_uuid(), :id, 'running') RETURNING id"""
DATASET = """INSERT INTO datasets
    (id, source_id, external_id, title, first_seen_run_id, last_seen_run_id, metadata_hash)
    VALUES (gen_random_uuid(), :source, :external, :title, :run, :run, 'h') RETURNING id"""


async def seed(connection: AsyncConnection, source: str = "a") -> Any:
    await connection.execute(text(SOURCE), {"id": source})
    return (await connection.execute(text(RUN), {"id": source})).scalar_one()


async def add(connection: AsyncConnection, run: Any, source: str, external: str, title: str) -> Any:
    values = {"source": source, "external": external, "title": title, "run": run}
    return (await connection.execute(text(DATASET), values)).scalar_one()


def test_models_and_migrations_agree(migrated: str) -> None:
    result = alembic(migrated, "check")
    assert result.returncode == 0, result.stdout + result.stderr


def test_migration_can_be_reverted_and_reapplied(migrated: str) -> None:
    for arguments in (("downgrade", "base"), ("upgrade", "head"), ("check",)):
        result = alembic(migrated, *arguments)
        assert result.returncode == 0, result.stderr


async def test_defaults_grant_nothing(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        run = await seed(connection)
        await add(connection, run, "a", "x", "Title")
        row = (
            await connection.execute(
                text(
                    "SELECT d.review_status::text, d.extraction_permission::text, "
                    "d.redistribution_permission::text, s.metadata_publication::text, "
                    "d.categories, d.licenses, d.publisher "
                    "FROM datasets d JOIN sources s USING (source_id)"
                )
            )
        ).one()
    assert tuple(row) == ("pending", "undetermined", "undetermined", "undetermined", [], [], None)


async def test_identity_is_unique_per_source(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        run_a = await seed(connection, "a")
        run_b = await seed(connection, "b")
        await add(connection, run_a, "a", "same", "Title")
        await add(connection, run_b, "b", "same", "Title")  # AC-06: another source
    with pytest.raises(IntegrityError, match="uq_datasets_source_id_external_id"):
        async with engine.begin() as connection:
            await add(connection, run_a, "a", "same", "Other")


@pytest.mark.parametrize(
    ("external", "title", "constraint"),
    [("x", "   ", "title_not_blank"), (" ", "Title", "external_id_not_blank")],
)
async def test_blank_identity_or_title_is_rejected(
    engine: AsyncEngine, external: str, title: str, constraint: str
) -> None:
    with pytest.raises(IntegrityError, match=constraint):
        async with engine.begin() as connection:
            run = await seed(connection)
            await add(connection, run, "a", external, title)


async def test_publication_requires_an_audited_decision(engine: AsyncEngine) -> None:
    with pytest.raises(IntegrityError, match="publication_is_audited"):
        async with engine.begin() as connection:
            await seed(connection)
            await connection.execute(text("UPDATE sources SET metadata_publication = 'allowed'"))


async def test_decisions_require_evidence(engine: AsyncEngine) -> None:
    with pytest.raises(IntegrityError, match="evidence_not_blank"):
        async with engine.begin() as connection:
            await seed(connection)
            await connection.execute(
                text(
                    "INSERT INTO permission_decisions (source_id, field, new_value, evidence, "
                    "decided_by, decided_at) VALUES ('a', 'f', 'denied', ' ', 'p', now())"
                )
            )


async def test_locators_and_observations_are_unique(engine: AsyncEngine) -> None:
    locator = text(
        "INSERT INTO access_locators (id, dataset_id, kind, url, source_field, status) "
        "VALUES (gen_random_uuid(), :dataset, 'web', :url, 'f', 'unverified')"
    )
    observation = text(
        "INSERT INTO dataset_observations (dataset_id, run_id, query_index, source_url) "
        "VALUES (:dataset, :run, 0, 'https://example.org')"
    )
    long_url = "https://example.org/" + "a" * 9000
    async with engine.begin() as connection:
        run = await seed(connection)
        dataset = await add(connection, run, "a", "x", "Title")
        await connection.execute(locator, {"dataset": dataset, "url": long_url})
        await connection.execute(observation, {"dataset": dataset, "run": run})
    for statement, values, name in (
        (locator, {"dataset": dataset, "url": long_url}, "uq_access_locators_identity"),
        (observation, {"dataset": dataset, "run": run}, "uq_dataset_observations"),
    ):
        with pytest.raises(IntegrityError, match=name):
            async with engine.begin() as connection:
                await connection.execute(statement, values)
