"""Catalog resources against PostgreSQL (AC-12 to AC-15, AC-26, AC-27, AC-31).

The catalog is the synthetic one of ``tests/fixtures/synthetic/seed.py``.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from fdh.api.app import app_factory, create_app
from fdh.domain.permissions import Permission, ReviewStatus, metadata_visible
from fdh.persistence.models import Dataset, Source
from fdh.persistence.queries import SqlQueryRepository
from fdh.persistence.session import create_engine, create_sessions
from tests.fixtures.synthetic import seed as synthetic

DATASETS = "/api/v1/datasets"


@dataclass
class Catalog:
    client: httpx.AsyncClient
    engine: AsyncEngine
    seeded: synthetic.Seeded

    async def get(self, path: str, **params: Any) -> Any:
        response = await self.client.get(path, params=params)
        assert response.status_code == 200, response.text
        return response.json()

    async def titles(self, **params: Any) -> list[str]:
        page = await self.get(DATASETS, page_size=100, **params)
        assert page["total"] == len(page["items"])
        return [item["title"] for item in page["items"]]

    def id(self, external_id: str) -> str:
        return str(self.seeded.ids[external_id])


async def ok() -> None:
    return None


@pytest.fixture
async def catalog(engine: AsyncEngine) -> AsyncIterator[Catalog]:
    seeded = await synthetic.seed(engine)
    reading = create_engine(engine.url, read_only=True)
    app = create_app(
        check_database=ok, queries=SqlQueryRepository(reading), allowed_hosts=["127.0.0.1"]
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        yield Catalog(client, engine, seeded)
    await reading.dispose()


async def test_pages_hold_twenty_records_by_default_and_at_most_a_hundred(
    catalog: Catalog,
) -> None:
    first = await catalog.get(DATASETS)
    assert (first["page"], first["page_size"], first["total"]) == (1, 20, synthetic.VISIBLE)
    assert len(first["items"]) == 20
    second = await catalog.get(DATASETS, page=2)
    assert len(second["items"]) == synthetic.VISIBLE - 20
    identifiers = [item["id"] for item in first["items"] + second["items"]]
    assert len(set(identifiers)) == synthetic.VISIBLE
    titles = [item["title"] for item in first["items"] + second["items"]]
    everything = await catalog.get(DATASETS, page_size=100)
    assert [item["title"] for item in everything["items"]] == titles
    beyond = await catalog.get(DATASETS, page=500)
    assert (beyond["items"], beyond["total"]) == ([], synthetic.VISIBLE)


@pytest.mark.parametrize(
    "params",
    [
        {"page_size": 101},
        {"page_size": 0},
        {"page": 0},
        {"page": 10001},
        {"page": "x"},
        {"q": "x" * 201},
        {"provider": "x" * 201},
        {"category": "x" * 201},
        {"q": "a\x00b"},
        {"provider": "a\x00b"},
        {"category": "a\x00b"},
    ],
)
async def test_invalid_parameters_are_refused(catalog: Catalog, params: dict[str, Any]) -> None:
    response = await catalog.client.get(DATASETS, params=params)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_parameters"
    assert "xxxxx" not in response.text


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("ejecucion", ["SINTÉTICO Ejecución presupuestal anual"]),
        ("INVERSIÓN", ["SINTÉTICO Inversión pública"]),
        ("yacimiento", ["SINTÉTICO 100% cobertura_rural"]),  # found in the description
        # Wildcards are ordinary characters, also after accents are removed.
        ("%", ["SINTÉTICO 100% cobertura_rural"]),
        ("_", ["SINTÉTICO 100% cobertura_rural"]),
        ("\uff05", ["SINTÉTICO 100% cobertura_rural"]),
        ("\uff3f", ["SINTÉTICO 100% cobertura_rural"]),
        ("\\", []),
        ("sin coincidencias", []),
        ("' OR 1=1 --", []),
    ],
)
async def test_text_search_ignores_accents_and_escapes_wildcards(
    catalog: Catalog, q: str, expected: list[str]
) -> None:
    assert await catalog.titles(q=q) == expected


async def test_an_empty_search_is_no_filter(catalog: Catalog) -> None:
    assert len(await catalog.titles(q="  ")) == synthetic.VISIBLE


@pytest.mark.parametrize(
    ("params", "count"),
    [
        ({"provider": "Proveedor Sintético Beta"}, 1),
        ({"provider": "Proveedor Sintético Alfa"}, synthetic.VISIBLE - 1),
        ({"provider": "proveedor sintético alfa"}, 0),
        ({"category": "participación ciudadana"}, 2),
        ({"category": "PARTICIPACIÓN CIUDADANA"}, 2),
        ({"category": "Economía"}, 1),  # a topic
        ({"category": "salud"}, 1),
        ({"category": "participación"}, 0),  # the whole value
        ({"category": "participación ciudadana", "q": "inversion"}, 1),
        ({"category": "salud", "provider": "Proveedor Sintético Beta", "q": "externa"}, 1),
        ({"category": "salud", "provider": "Proveedor Sintético Alfa"}, 0),
    ],
)
async def test_filters_work_alone_and_combined(
    catalog: Catalog, params: dict[str, str], count: int
) -> None:
    assert len(await catalog.titles(**params)) == count


async def test_a_summary_carries_licences_attribution_and_review(catalog: Catalog) -> None:
    (item,) = (await catalog.get(DATASETS, q="presupuestal"))["items"]
    assert item["review_status"] == "pending"
    assert [licence["name"] for licence in item["licenses"]] == [
        "Licencia sintética A",
        "Licencia sintética B",
    ]
    assert item["attribution"] == {
        "text": "Atribución sintética de Proveedor Sintético Alfa",
        "data_sources": [],
        "data_updated_at": "2025-12-31T00:00:00Z",
        "citation_requirement": "Citar como fuente sintética.",
    }
    assert (item["provider"], item["platform"]) == ("Proveedor Sintético Alfa", "socrata")


async def test_detail_returns_all_metadata_conditions_and_provenance(catalog: Catalog) -> None:
    detail = await catalog.get(f"{DATASETS}/{catalog.id('alpha-budget')}")
    assert detail["description"] == synthetic.BUDGET.description
    assert detail["tags"] == ["presupuesto", "sintético"]
    assert detail["official_url"] == "https://data.example.org/d/alpha-budget"
    assert detail["created_at"] == "2025-12-02T00:00:00Z"
    assert (detail["published_at"], detail["updated_at"]) == (None, None)
    assert (detail["access_conditions"], detail["redistribution_conditions"]) == (None, None)
    assert detail["extraction_permission"] == detail["redistribution_permission"] == "undetermined"
    assert detail["source"] == {
        "official_url": "https://www.example.org",
        "verified_at": "2026-01-01",
        "access_conditions": "Condición sintética de acceso",
        "redistribution_conditions": None,
        "license_name": None,
        "license_url": None,
        "terms_url": "https://example.org/terms",
        "terms_checked_on": "2026-01-01",
    }
    assert [(item["kind"], item["status"]) for item in detail["locators"]] == [
        ("api", "invalid"),
        ("web", "unverified"),
    ]
    provenance = detail["provenance"]
    total = synthetic.EXTRA_RUNS + 3  # once per extra run, twice truncated, once partial
    assert (provenance["total"], len(provenance["items"])) == (total, 20)
    newest = provenance["items"][0]
    assert newest["run_id"] == str(catalog.seeded.runs["partial"])
    assert newest["query_term"] == "presupuesto"
    assert newest["source_url"] == "https://api.example.org/catalog?q=presupuesto"
    moments = [item["observed_at"] for item in provenance["items"]]
    assert moments == sorted(moments, reverse=True)


async def test_unknown_values_and_external_licences_are_preserved(catalog: Catalog) -> None:
    unknown = await catalog.get(f"{DATASETS}/{catalog.id('alpha-investment')}")
    assert (unknown["description"], unknown["publisher"], unknown["licenses"]) == (None, None, [])
    external = await catalog.get(f"{DATASETS}/{catalog.id('beta-external')}")
    assert external["licenses"] == [
        {"name": None, "url": "https://example.org/external", "note": "Licencia externa"}
    ]
    assert external["attribution"]["data_sources"] == ["Organización Sintética"]
    assert external["source"]["license_name"] == "Licencia sintética de la fuente"


async def test_provenance_is_paginated(catalog: Catalog) -> None:
    path = f"{DATASETS}/{catalog.id('alpha-budget')}/provenance"
    first = await catalog.get(path)
    second = await catalog.get(path, page=2)
    assert first["total"] == second["total"] == synthetic.EXTRA_RUNS + 3
    assert len(first["items"]) == 20
    assert len(second["items"]) == first["total"] - 20
    refused = await catalog.client.get(path, params={"page_size": 101})
    assert refused.status_code == 422


async def test_unknown_and_malformed_identifiers(catalog: Catalog) -> None:
    for path in (f"{DATASETS}/{uuid4()}", f"{DATASETS}/{uuid4()}/provenance"):
        response = await catalog.client.get(path)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"
    assert (await catalog.client.get(f"{DATASETS}/not-a-uuid")).status_code == 422


async def test_hidden_datasets_do_not_exist_anywhere(catalog: Catalog) -> None:
    listed = await catalog.get(DATASETS, page_size=100)
    for external_id in synthetic.HIDDEN_IDENTIFIERS:
        identifier = catalog.id(external_id)
        assert identifier not in {item["id"] for item in listed["items"]}
        for path in (f"{DATASETS}/{identifier}", f"{DATASETS}/{identifier}/provenance"):
            assert (await catalog.client.get(path)).status_code == 404
    for q in ("Restringido", "Oculto", "denegada"):
        assert await catalog.titles(q=q) == []
    for category in ("categoría restringida", "categoría oculta", "categoría denegada"):
        assert await catalog.titles(category=category) == []
    assert await catalog.titles(provider="Proveedor Sintético Oculto") == []
    providers = await catalog.get("/api/v1/providers")
    assert providers["items"] == ["Proveedor Sintético Alfa", "Proveedor Sintético Beta"]
    categories = await catalog.get("/api/v1/categories", page_size=100)
    assert not any(
        word in value for value in categories["items"] for word in ("restringida", "oculta", "dene")
    )


async def test_revoking_a_source_hides_it_at_once(catalog: Catalog) -> None:
    async with create_sessions(catalog.engine)() as session, session.begin():
        await session.execute(
            update(Source)
            .where(Source.source_id == synthetic.BETA)
            .values(
                metadata_publication=Permission.UNDETERMINED,
                publication_evidence_url=None,
                publication_declared_by=None,
                publication_declared_on=None,
            )
        )
    assert len(await catalog.titles()) == synthetic.VISIBLE - 1
    response = await catalog.client.get(f"{DATASETS}/{catalog.id('beta-external')}")
    assert response.status_code == 404


@pytest.mark.parametrize("publication", list(Permission))
@pytest.mark.parametrize("review", list(ReviewStatus))
async def test_the_query_follows_the_domain_visibility_rule(
    catalog: Catalog, publication: Permission, review: ReviewStatus
) -> None:
    async with create_sessions(catalog.engine)() as session, session.begin():
        await session.execute(
            update(Source)
            .where(Source.source_id == synthetic.BETA)
            .values(
                metadata_publication=publication,
                publication_evidence_url="https://example.org/e",
                publication_declared_by="synthetic person",
                publication_declared_on=synthetic.START.date(),
            )
        )
        await session.execute(
            update(Dataset)
            .where(Dataset.external_id == "beta-external")
            .values(review_status=review)
        )
    response = await catalog.client.get(f"{DATASETS}/{catalog.id('beta-external')}")
    assert response.status_code == (200 if metadata_visible(publication, review) else 404)
    if response.status_code == 200:
        assert response.json()["review_status"] == review.value


async def test_providers_and_categories_are_paginated(catalog: Catalog) -> None:
    page = await catalog.get("/api/v1/providers", page_size=1, page=2)
    assert (page["items"], page["total"]) == (["Proveedor Sintético Beta"], 2)
    categories = await catalog.get("/api/v1/categories")
    folded = [value.casefold() for value in categories["items"]]
    # Variants that differ only in case are offered once.
    assert sorted(folded) == [
        "economía",
        "hacienda y crédito público",
        "participación ciudadana",
        "salud",
    ]
    assert categories["total"] == 4
    found = await catalog.get("/api/v1/categories", q="participacion")
    assert [value.casefold() for value in found["items"]] == ["participación ciudadana"]
    for path in ("/api/v1/providers", "/api/v1/categories"):
        assert (await catalog.client.get(path, params={"page_size": 101})).status_code == 422


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_the_api_offers_no_writes(catalog: Catalog, method: str) -> None:
    for path in (DATASETS, f"{DATASETS}/{catalog.id('alpha-budget')}", "/api/v1/runs"):
        response = await catalog.client.request(method, path)
        assert response.status_code == 405
        assert response.json()["error"]["code"] == "method_not_allowed"


async def test_responses_are_not_cached(catalog: Catalog) -> None:
    response = await catalog.client.get(DATASETS)
    assert response.headers["cache-control"] == "no-store"


async def test_the_connections_of_the_api_cannot_write(engine: AsyncEngine) -> None:
    reading = create_engine(engine.url, read_only=True)
    try:
        with pytest.raises(DBAPIError, match="read-only transaction"):
            async with reading.begin() as connection:
                await connection.execute(text("DELETE FROM datasets"))
    finally:
        await reading.dispose()


async def test_the_application_reads_from_the_environment(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    await synthetic.seed(engine)
    monkeypatch.setenv("FDH_API_ALLOWED_HOSTS", "127.0.0.1")
    app = app_factory()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            assert (await client.get("/health")).json() == {"status": "ok"}
            assert (await client.get(DATASETS)).json()["total"] == synthetic.VISIBLE


async def test_an_unreachable_database_is_unavailable_without_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FDH_DB_PORT", "1")
    monkeypatch.setenv("FDH_DB_PASSWORD", "fake-password-135790")
    monkeypatch.setenv("FDH_API_ALLOWED_HOSTS", "127.0.0.1")
    app = app_factory()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            for path in ("/health", DATASETS, "/api/v1/runs", f"{DATASETS}/{uuid4()}"):
                response = await client.get(path)
                assert response.status_code == 503, path
                assert response.json()["error"]["code"] == "unavailable"
                assert "fake-password" not in response.text
