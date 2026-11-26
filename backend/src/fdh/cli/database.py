"""Database access of the local commands, from the environment."""

from sqlalchemy.ext.asyncio import AsyncEngine

from fdh.persistence.session import create_engine, database_url
from fdh.settings.env import Settings


def database_engine(settings: Settings) -> AsyncEngine:
    return create_engine(
        database_url(
            host=settings.db_host,
            port=settings.db_port,
            name=settings.db_name,
            user=settings.db_user,
            password=settings.db_password.get_secret_value(),
        )
    )
