"""Error format of the API without a database: nothing internal is ever shown."""

from typing import Any
from uuid import uuid4

import httpx
import pytest

from fdh.api.app import create_app
from fdh.controlplane.catalog import StorageUnavailable


async def ok() -> None:
    return None


class Failing:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def __getattr__(self, name: str) -> Any:
        async def fail(*args: object, **kwargs: object) -> None:
            raise self.error

        return fail


async def get(error: Exception, path: str) -> httpx.Response:
    app = create_app(check_database=ok, queries=Failing(error), allowed_hosts=["127.0.0.1"])
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        return await client.get(path)


PATHS = [
    "/api/v1/datasets",
    f"/api/v1/datasets/{uuid4()}",
    f"/api/v1/datasets/{uuid4()}/provenance",
    "/api/v1/providers",
    "/api/v1/categories",
    "/api/v1/runs",
    f"/api/v1/runs/{uuid4()}",
]


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (StorageUnavailable("password=fake-secret-24680"), 503, "unavailable"),
        (RuntimeError("password=fake-secret-24680"), 500, "internal_error"),
    ],
)
async def test_failures_are_visible_and_sanitised(
    path: str, error: Exception, status: int, code: str, caplog: pytest.LogCaptureFixture
) -> None:
    response = await get(error, path)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert "fake-secret" not in response.text
    assert "fake-secret" not in caplog.text


@pytest.mark.parametrize("path", ["/unknown", "/api/v1/unknown", "/docs", "/redoc"])
async def test_unknown_routes_use_the_same_format(path: str) -> None:
    response = await get(RuntimeError(), path)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
