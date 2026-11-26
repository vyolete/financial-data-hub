"""Database engines. Credentials are passed as values and never logged."""

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def database_url(*, host: str, port: int, name: str, user: str, password: str) -> URL:
    return URL.create(
        "postgresql+asyncpg",
        username=user,
        password=password or None,
        host=host,
        port=port,
        database=name,
    )


def create_engine(url: URL, *, read_only: bool = False) -> AsyncEngine:
    engine = create_async_engine(url, pool_pre_ping=True, connect_args={"timeout": 5})
    return engine.execution_options(postgresql_readonly=True) if read_only else engine


def create_sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
