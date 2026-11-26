"""Health endpoint and host validation, without a database."""

from typing import Any

import httpx
import pytest

from fdh.api.app import create_app

NO_QUERIES: Any = None  # these tests never read the catalog


async def ok() -> None:
    return None


async def broken() -> None:
    raise ConnectionError("password=fake-secret-555 refused")


async def get(app: object, path: str = "/health", host: str = "127.0.0.1") -> httpx.Response:
    transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url=f"http://{host}") as client:
        return await client.get(path)


async def test_healthy() -> None:
    app = create_app(check_database=ok, queries=NO_QUERIES, allowed_hosts=["127.0.0.1"])
    response = await get(app)
    assert (response.status_code, response.json()) == (200, {"status": "ok"})


async def test_unavailable_database_is_visible_and_sanitised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = create_app(check_database=broken, queries=NO_QUERIES, allowed_hosts=["127.0.0.1"])
    response = await get(app)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "unavailable"
    assert "fake-secret" not in response.text
    assert "database check failed" in caplog.text


async def test_unknown_host_is_rejected() -> None:
    app = create_app(
        check_database=ok, queries=NO_QUERIES, allowed_hosts=["127.0.0.1", "localhost"]
    )
    assert (await get(app, host="attacker.example")).status_code == 400


@pytest.mark.parametrize("path", ["/docs", "/redoc"])
async def test_interactive_documentation_is_not_exposed(path: str) -> None:
    app = create_app(check_database=ok, queries=NO_QUERIES, allowed_hosts=["127.0.0.1"])
    assert (await get(app, path)).status_code == 404


async def test_only_read_methods_exist() -> None:
    app = create_app(check_database=ok, queries=NO_QUERIES, allowed_hosts=["127.0.0.1"])
    methods = {m for path in app.openapi()["paths"].values() for m in path}
    assert methods == {"get"}
