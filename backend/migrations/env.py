"""Alembic environment. The connection comes from the FDH_DB_* variables."""

import asyncio

from alembic import context
from sqlalchemy.engine import Connection

from fdh.observability.logging import configure_logging
from fdh.persistence.models import Base
from fdh.persistence.session import create_engine, database_url
from fdh.settings.env import Settings


def run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    settings = Settings()
    configure_logging(settings.log_level)
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
        async with engine.connect() as connection:
            await connection.run_sync(run)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    raise SystemExit("offline migrations are not supported")
asyncio.run(run_online())
