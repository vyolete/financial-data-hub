"""The API reaches PostgreSQL through read-only transactions (AC-15)."""

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from fdh.api.app import app_factory
from fdh.persistence.session import create_engine, database_url
from fdh.settings.env import Settings


async def test_health_uses_the_database(migrated: str) -> None:
    app = app_factory()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            response = await client.get("/health")
    assert (response.status_code, response.json()) == (200, {"status": "ok"})


async def test_read_only_engine_rejects_writes(migrated: str) -> None:
    settings = Settings()
    engine = create_engine(
        database_url(
            host=settings.db_host,
            port=settings.db_port,
            name=migrated,
            user=settings.db_user,
            password=settings.db_password.get_secret_value(),
        ),
        read_only=True,
    )
    try:
        with pytest.raises(DBAPIError, match="read-only transaction"):
            async with engine.begin() as connection:
                await connection.execute(text("DELETE FROM sources"))
    finally:
        await engine.dispose()
