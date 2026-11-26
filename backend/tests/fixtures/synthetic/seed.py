"""Load an invented catalog for API tests, the smoke test and the browser check (T055).

Every name, dataset and decision here is SYNTHETIC. Nothing describes a real provider. The
command refuses to run on a database that holds data of any other source.

    python tests/fixtures/synthetic/seed.py   # uses the FDH_DB_* variables
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from fdh.controlplane.runs import ObservedPage, RunError, RunMetrics
from fdh.controlplane.sources import RegisteredSource, SyncPlan, plan_source_sync
from fdh.domain.datasets import (
    AccessLocator,
    DatasetDates,
    DeclaredLicense,
    DiscoveredDataset,
)
from fdh.domain.permissions import Permission, ReviewStatus
from fdh.domain.sources import DiscoveryQuery, PublicationDecision, SourceDefinition
from fdh.domain.status import RunStatus
from fdh.persistence.catalog import SqlCatalogRepository
from fdh.persistence.models import Dataset, Run
from fdh.persistence.runs import SqlRunRepository
from fdh.persistence.session import create_engine, create_sessions, database_url
from fdh.persistence.sources import SqlSourceRepository
from fdh.settings.env import Settings

PREFIX = "synthetic-"
ALPHA, BETA = "synthetic-alpha", "synthetic-beta"
HIDDEN, DENIED = "synthetic-hidden", "synthetic-denied"
START = datetime(2026, 1, 1, tzinfo=UTC)
QUERIES = (DiscoveryQuery("presupuesto"), DiscoveryQuery("economia"))
FILLERS = 23
EXTRA_RUNS = 21  # more than one page of provenance and of runs


def definition(source_id: str, provider: str, publication: Permission) -> SourceDefinition:
    audited = publication is not Permission.UNDETERMINED
    return SourceDefinition(
        source_id=source_id,
        provider=provider,
        platform="data360" if source_id == BETA else "socrata",
        base_url="https://api.example.org/catalog",
        allowed_hosts=("api.example.org",),
        official_url="https://www.example.org",
        verified_at=date(2026, 1, 1),
        publication=PublicationDecision(
            publication,
            "synthetic person" if audited else None,
            date(2026, 1, 1) if audited else None,
            "https://example.org/synthetic-decision" if audited else None,
        ),
        attribution=f"Atribución sintética de {provider}",
        access_conditions="Condición sintética de acceso" if source_id == ALPHA else None,
        redistribution_conditions=None,
        license_name="Licencia sintética de la fuente" if source_id == BETA else None,
        license_url="https://example.org/source-licence" if source_id == BETA else None,
        terms_url="https://example.org/terms" if source_id == ALPHA else None,
        terms_checked_on=date(2026, 1, 1) if source_id == ALPHA else None,
    )


SOURCES = (
    definition(ALPHA, "Proveedor Sintético Alfa", Permission.ALLOWED),
    definition(BETA, "Proveedor Sintético Beta", Permission.ALLOWED),
    definition(HIDDEN, "Proveedor Sintético Oculto", Permission.UNDETERMINED),
    definition(DENIED, "Proveedor Sintético Denegado", Permission.DENIED),
)

BUDGET = DiscoveredDataset(
    external_id="alpha-budget",
    title="SINTÉTICO Ejecución presupuestal anual",
    description="Descripción inventada.\n<script>alert('sintético')</script>",
    publisher="Entidad Sintética",
    official_url="https://data.example.org/d/alpha-budget",
    categories=("Hacienda y Crédito Público",),
    tags=("presupuesto", "sintético"),
    licenses=(
        DeclaredLicense("Licencia sintética A", "https://example.org/licence-a", "Nota sintética"),
        DeclaredLicense("Licencia sintética B", "http://example.org/insecure-licence"),
    ),
    citation_requirement="Citar como fuente sintética.",
    dates=DatasetDates(
        created_at=START - timedelta(days=30), data_updated_at=START - timedelta(days=1)
    ),
    locators=(
        AccessLocator("web", "https://data.example.org/d/alpha-budget", "permalink"),
        AccessLocator("api", "http://data.example.org/insecure", "link"),
    ),
)
INVESTMENT = DiscoveredDataset(
    external_id="alpha-investment",
    title="SINTÉTICO Inversión pública",
    categories=("Participación Ciudadana",),
    topics=("Economía",),
)
PERCENT = DiscoveredDataset(
    external_id="alpha-percent",
    title="SINTÉTICO 100% cobertura_rural",
    description="Texto con la palabra yacimiento.",
    categories=("participación ciudadana",),
)
RESTRICTED = DiscoveredDataset(
    external_id="alpha-restricted",
    title="SINTÉTICO Restringido",
    categories=("Categoría restringida",),
)
EXTERNAL = DiscoveredDataset(
    external_id="beta-external",
    title="SINTÉTICO Indicador con licencia externa",
    topics=("Salud",),
    data_sources=("Organización Sintética",),
    licenses=(DeclaredLicense(None, "https://example.org/external", "Licencia externa"),),
)
OF_HIDDEN = DiscoveredDataset(
    "hidden-one", "SINTÉTICO Oculto por su fuente", categories=("Categoría oculta",)
)
OF_DENIED = DiscoveredDataset(
    "denied-one", "SINTÉTICO De fuente denegada", categories=("Categoría denegada",)
)
ALPHA_DATASETS = (
    BUDGET,
    INVESTMENT,
    PERCENT,
    RESTRICTED,
    *tuple(
        DiscoveredDataset(
            f"alpha-series-{n:02}",
            f"SINTÉTICO Serie {n:02}",
            categories=("Hacienda y Crédito Público",),
        )
        for n in range(1, FILLERS + 1)
    ),
)
VISIBLE = len(ALPHA_DATASETS) - 1 + 1  # all of alpha but the restricted one, plus beta
HIDDEN_IDENTIFIERS = ("alpha-restricted", "hidden-one", "denied-one")


class NotSynthetic(Exception):
    """The database holds data that this script did not invent."""


@dataclass(frozen=True)
class Seeded:
    ids: dict[str, UUID]  # dataset id by external identifier
    runs: dict[str, UUID]


async def seed(engine: AsyncEngine) -> Seeded:
    sessions = create_sessions(engine)
    async with sessions() as session:
        for column in (Dataset.source_id, Run.source_id):
            found = await session.scalar(
                select(column).where(column.notlike(f"{PREFIX}%")).limit(1)
            )
            if found:
                raise NotSynthetic("the database already holds data of other sources")

    def plan(registered: list[RegisteredSource] | object) -> SyncPlan:
        # Sources that are not synthetic are left exactly as they are.
        assert isinstance(registered, list)
        own = [source for source in registered if source.source_id.startswith(PREFIX)]
        return plan_source_sync(SOURCES, own, today=date(2026, 1, 1))

    await SqlSourceRepository(sessions).synchronise(plan)
    runs = SqlRunRepository(engine)
    catalog = SqlCatalogRepository(sessions)
    clock = [START]

    async def page(
        run_id: UUID,
        source_id: str,
        datasets: tuple[DiscoveredDataset, ...],
        query: int = 0,
        rejected: int = 0,
        total: int | None = None,
    ) -> None:
        clock[0] += timedelta(minutes=1)
        await catalog.store_page(
            ObservedPage(
                run_id=run_id,
                source_id=source_id,
                query_index=query,
                source_url=f"https://api.example.org/catalog?q={QUERIES[query].term}",
                request_summary={"synthetic": True},
                observed_at=clock[0],
                datasets=datasets,
                rejected=rejected,
                total_declared=total,
            )
        )

    created: dict[str, UUID] = {}
    for source_id, datasets in ((HIDDEN, (OF_HIDDEN,)), (DENIED, (OF_DENIED,))):
        run_id = await runs.start(source_id, {"synthetic": True}, QUERIES)
        await page(run_id, source_id, datasets)
        await runs.finish(run_id, RunStatus.SUCCEEDED, RunMetrics(1, 40, 5, {}))

    # Runs recorded before the metrics existed keep them unknown.
    historical = await runs.start(BETA, {"synthetic": True}, QUERIES)
    await page(historical, BETA, (EXTERNAL,))
    await runs.finish(historical, RunStatus.SUCCEEDED, RunMetrics())
    created["historical"] = historical

    for _ in range(EXTRA_RUNS):
        run_id = await runs.start(ALPHA, {"synthetic": True}, QUERIES)
        await page(run_id, ALPHA, (BUDGET,))
        await runs.finish(run_id, RunStatus.SUCCEEDED, RunMetrics(1, 40, 5, {}))

    truncated = await runs.start(ALPHA, {"synthetic": True}, QUERIES)
    await page(truncated, ALPHA, ALPHA_DATASETS, total=900)
    await page(truncated, ALPHA, (BUDGET,), query=1, total=1)
    await runs.mark_truncated(truncated, 0)
    await runs.finish(truncated, RunStatus.SUCCEEDED, RunMetrics(2, 1500, 120, {}))
    created["truncated"] = truncated

    partial = await runs.start(ALPHA, {"synthetic": True}, QUERIES)
    await page(partial, ALPHA, (BUDGET,), rejected=2, total=3)
    await runs.record_failure(
        partial, RunError("rate_limited", "synthetic provider limit", 1, 429, 4)
    )
    await runs.finish(
        partial,
        RunStatus.PARTIAL,
        RunMetrics(5, 8200, 30, {"missing_title": 1, "unexpected_type": 1}),
    )
    created["partial"] = partial

    failed = await runs.start(BETA, {"synthetic": True}, QUERIES)
    await runs.record_failure(failed, RunError("timeout", "synthetic timeout", 0, None, 4))
    await runs.finish(failed, RunStatus.FAILED, RunMetrics(4, 47000, 0, {}))
    created["failed"] = failed

    created["running"] = await runs.start(BETA, {"synthetic": True}, QUERIES)

    async with sessions() as session, session.begin():
        await session.execute(
            update(Dataset)
            .where(Dataset.external_id == RESTRICTED.external_id)
            .values(review_status=ReviewStatus.RESTRICTED)
        )
    async with sessions() as session:
        rows = await session.execute(select(Dataset.external_id, Dataset.id))
        return Seeded({row[0]: row[1] for row in rows}, created)


async def main() -> int:
    settings = Settings()
    engine = create_engine(
        database_url(
            host=settings.db_host,
            port=settings.db_port,
            name=settings.db_name,
            user=settings.db_user,
            password=settings.db_password.get_secret_value(),
        )
    )
    try:
        seeded = await seed(engine)
    except NotSynthetic as error:
        print(f"refused: {error}")
        return 1
    finally:
        await engine.dispose()
    print(
        json.dumps(
            {
                "synthetic": True,
                "visible_datasets": VISIBLE,
                "hidden_ids": [str(seeded.ids[name]) for name in HIDDEN_IDENTIFIERS],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
