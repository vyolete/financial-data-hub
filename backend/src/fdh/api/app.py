"""Read-only HTTP API. This increment only exposes the health of the service."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from fdh.observability.logging import configure_logging
from fdh.persistence.session import create_engine, database_url
from fdh.settings.env import Settings

log = logging.getLogger(__name__)
DatabaseCheck = Callable[[], Awaitable[None]]


def create_app(
    *,
    check_database: DatabaseCheck,
    allowed_hosts: list[str],
    on_shutdown: Callable[[], Awaitable[None]] | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if on_shutdown:
            await on_shutdown()

    # The interactive documentation pages load third-party scripts: keep them off.
    app = FastAPI(
        title="Financial Data Hub Catalog API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts, www_redirect=False)

    @app.get("/health", operation_id="getHealth")
    async def health(_: Request) -> JSONResponse:
        try:
            await check_database()
        except Exception:
            log.exception("database check failed", extra={"event": "health_check_failed"})
            return JSONResponse(
                {"error": {"code": "unavailable", "message": "database unavailable"}}, 503
            )
        return JSONResponse({"status": "ok"})

    return app


def app_factory() -> FastAPI:
    """Application wired from the environment (used by Uvicorn)."""
    settings = Settings()
    configure_logging(settings.log_level)
    engine = create_engine(
        database_url(
            host=settings.db_host,
            port=settings.db_port,
            name=settings.db_name,
            user=settings.db_user,
            password=settings.db_password.get_secret_value(),
        ),
        read_only=True,
    )

    async def check_database() -> None:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    return create_app(
        check_database=check_database,
        allowed_hosts=settings.allowed_hosts,
        on_shutdown=engine.dispose,
    )
