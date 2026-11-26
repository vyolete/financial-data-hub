"""Read-only HTTP API for the local catalog."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from fdh.api.routes.datasets import dataset_routes
from fdh.api.routes.parameters import UNAVAILABLE
from fdh.api.routes.runs import run_routes
from fdh.api.schemas import Health
from fdh.controlplane.catalog import CatalogQueries, ResourceNotFound, StorageUnavailable
from fdh.observability.logging import configure_logging
from fdh.persistence.queries import SqlQueryRepository
from fdh.persistence.session import create_engine, database_url
from fdh.settings.env import Settings

log = logging.getLogger(__name__)
DatabaseCheck = Callable[[], Awaitable[None]]


def create_app(
    *,
    check_database: DatabaseCheck,
    allowed_hosts: list[str],
    queries: CatalogQueries,
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

    def error(
        status: int, code: str, message: str, headers: Mapping[str, str] | None = None
    ) -> JSONResponse:
        return JSONResponse({"error": {"code": code, "message": message}}, status, headers)

    @app.middleware("http")
    async def safe_response(request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            response = await call_next(request)
        except Exception as exc:
            log.error(
                "unexpected API failure",
                extra={"event": "api_failure", "error_type": type(exc).__name__},
            )
            response = error(500, "internal_error", "internal server error")
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ResourceNotFound)
    async def missing(_: Request, exc: ResourceNotFound) -> JSONResponse:
        return error(404, "not_found", "resource not found")

    @app.exception_handler(StorageUnavailable)
    async def unavailable(_: Request, exc: StorageUnavailable) -> JSONResponse:
        log.warning("catalog read failed", extra={"event": "catalog_read_failed"})
        return error(503, "unavailable", "database unavailable")

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, exc: RequestValidationError) -> JSONResponse:
        return error(422, "invalid_parameters", "invalid request parameters")

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return error(404, "not_found", "resource not found")
        if exc.status_code == 405:
            return error(405, "method_not_allowed", "method not allowed", exc.headers)
        return error(exc.status_code, "request_failed", "request failed", exc.headers)

    @app.get("/health", operation_id="getHealth", response_model=Health, responses=UNAVAILABLE)
    async def health() -> Health | Response:
        try:
            await check_database()
        except Exception:
            log.warning("database check failed", extra={"event": "health_check_failed"})
            return error(503, "unavailable", "database unavailable")
        return Health(status="ok")

    app.include_router(dataset_routes(queries))
    app.include_router(run_routes(queries))

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
        queries=SqlQueryRepository(engine),
    )
