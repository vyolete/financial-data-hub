"""A fresh PostgreSQL database per test, migrated with Alembic.

Needs a reachable PostgreSQL 18 (see FDH_DB_* variables). There is no substitute engine and
the tests fail, rather than skip, when the database is unavailable.
"""

import asyncio
import logging
import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from fdh.persistence.session import create_engine, database_url
from fdh.settings.env import Settings

BACKEND = Path(__file__).resolve().parents[2]


def alembic(database: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=BACKEND,
        env={**os.environ, "FDH_DB_NAME": database},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


async def admin(statement: str) -> None:
    settings = Settings()
    connection = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password.get_secret_value() or None,
        database="postgres",
        timeout=5,
    )
    try:
        await connection.execute(statement)
    finally:
        await connection.close()


@pytest.fixture
def database() -> Iterator[str]:
    """Name of an empty database, dropped afterwards."""
    name = f"fdh_test_{uuid.uuid4().hex}"
    try:
        asyncio.run(admin(f'CREATE DATABASE "{name}"'))
    except (OSError, asyncpg.PostgresError) as error:
        pytest.fail(
            f"PostgreSQL is not available ({type(error).__name__}). "
            "Start it with `docker compose up -d db` and set FDH_DB_PASSWORD."
        )
    try:
        yield name
    finally:
        asyncio.run(admin(f'DROP DATABASE "{name}" WITH (FORCE)'))


@pytest.fixture
def migrated(database: str, monkeypatch: pytest.MonkeyPatch) -> str:
    result = alembic(database, "upgrade", "head")
    assert result.returncode == 0, result.stderr
    monkeypatch.setenv("FDH_DB_NAME", database)
    return database


@pytest.fixture
async def engine(migrated: str) -> AsyncIterator[AsyncEngine]:
    settings = Settings()
    created = create_engine(
        database_url(
            host=settings.db_host,
            port=settings.db_port,
            name=migrated,
            user=settings.db_user,
            password=settings.db_password.get_secret_value(),
        )
    )
    yield created
    await created.dispose()


@pytest.fixture(autouse=True)
def restore_logging() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    root.handlers, root.level = handlers, level
