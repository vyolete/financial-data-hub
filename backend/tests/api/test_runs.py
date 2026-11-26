"""Run resources against PostgreSQL (AC-09, AC-15, AC-30, AC-40). Synthetic data."""

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from fdh.api.app import create_app
from fdh.persistence.models import Run
from fdh.persistence.queries import SqlQueryRepository
from fdh.persistence.session import create_engine
from tests.fixtures.synthetic import seed as synthetic

RUNS = "/api/v1/runs"
TOTAL = synthetic.EXTRA_RUNS + 7


async def ok() -> None:
    return None


@pytest.fixture
async def api(engine: AsyncEngine) -> AsyncIterator[tuple[httpx.AsyncClient, synthetic.Seeded]]:
    seeded = await synthetic.seed(engine)
    reading = create_engine(engine.url, read_only=True)
    app = create_app(
        check_database=ok, queries=SqlQueryRepository(reading), allowed_hosts=["127.0.0.1"]
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        yield client, seeded
    await reading.dispose()


Api = tuple[httpx.AsyncClient, synthetic.Seeded]


async def get(api: Api, path: str = RUNS, **params: Any) -> Any:
    response = await api[0].get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def test_runs_are_listed_newest_first_and_paginated(api: Api) -> None:
    first = await get(api)
    assert (first["page"], first["page_size"], first["total"]) == (1, 20, TOTAL)
    second = await get(api, page=2)
    runs = first["items"] + second["items"]
    assert len({run["id"] for run in runs}) == TOTAL
    starts = [run["started_at"] for run in runs]
    assert starts == sorted(starts, reverse=True)
    assert runs[0]["id"] == str(api[1].runs["running"])


async def test_every_outcome_is_distinguishable_with_its_counts_and_metrics(api: Api) -> None:
    runs = {run["id"]: run for run in (await get(api, page_size=100))["items"]}
    by_name = {name: runs[str(run_id)] for name, run_id in api[1].runs.items()}
    assert {name: run["status"] for name, run in by_name.items()} == {
        "historical": "succeeded",
        "truncated": "succeeded",
        "partial": "partial",
        "failed": "failed",
        "running": "running",
    }
    truncated = by_name["truncated"]
    assert truncated["truncated"] is True
    assert (truncated["requests"], truncated["duration_ms"], truncated["persistence_ms"]) == (
        2,
        1500,
        120,
    )
    partial = by_name["partial"]
    assert (partial["rejected"], partial["failures"], partial["truncated"]) == (2, 1, False)
    # Unknown is null, never zero.
    for name in ("historical", "running"):
        run = by_name[name]
        assert (run["requests"], run["duration_ms"], run["persistence_ms"]) == (None, None, None)
    assert by_name["running"]["finished_at"] is None
    assert by_name["failed"]["persistence_ms"] == 0


async def test_detail_returns_queries_errors_and_rejections(api: Api) -> None:
    partial = await get(api, f"{RUNS}/{api[1].runs['partial']}")
    assert partial["rejection_reasons"] == {"missing_title": 1, "unexpected_type": 1}
    assert partial["errors"] == [
        {
            "code": "rate_limited",
            "message": "synthetic provider limit",
            "query_index": 1,
            "http_status": 429,
            "attempts": 4,
        }
    ]
    truncated = await get(api, f"{RUNS}/{api[1].runs['truncated']}")
    assert truncated["queries"][0] == {
        "query_index": 0,
        "term": "presupuesto",
        "pages_processed": 1,
        "total_declared": 900,
        "truncated": True,
    }
    assert truncated["rejection_reasons"] == {}
    historical = await get(api, f"{RUNS}/{api[1].runs['historical']}")
    assert historical["rejection_reasons"] is None


async def test_run_detail_redacts_credentials_in_historical_errors(
    api: Api, engine: AsyncEngine
) -> None:
    run_id = api[1].runs["failed"]
    async with engine.begin() as connection:
        await connection.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(
                errors=[
                    {
                        "code": "timeout",
                        "message": "request failed: token=fake-historical-24680",
                        "query_index": 0,
                        "http_status": None,
                        "attempts": 4,
                    }
                ]
            )
        )
    response = await api[0].get(f"{RUNS}/{run_id}")
    assert response.status_code == 200
    assert "fake-historical" not in response.text
    assert response.json()["errors"][0]["message"] == "request failed: token=[hidden]"


async def test_runs_can_be_filtered_by_source(api: Api) -> None:
    page = await get(api, source_id=synthetic.BETA)
    assert page["total"] == 3
    assert {run["source_id"] for run in page["items"]} == {synthetic.BETA}
    assert (await get(api, source_id="unknown"))["items"] == []


async def test_runs_of_hidden_sources_remain_visible(api: Api) -> None:
    assert (await get(api, source_id=synthetic.HIDDEN))["total"] == 1


@pytest.mark.parametrize(
    ("path", "status"),
    [
        (f"{RUNS}/{uuid4()}", 404),
        (f"{RUNS}/not-a-uuid", 422),
        (f"{RUNS}?page_size=101", 422),
        (f"{RUNS}?page=0", 422),
        (f"{RUNS}?source_id={'x' * 101}", 422),
        (f"{RUNS}?source_id=%00", 422),
    ],
)
async def test_errors(api: Api, path: str, status: int) -> None:
    response = await api[0].get(path)
    assert response.status_code == status
    assert set(response.json()["error"]) == {"code", "message"}
