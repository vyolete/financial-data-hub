"""Discovery run routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path

from fdh.api.routes.parameters import COLLECTION, RESOURCE, Page, Size, SourceId
from fdh.api.schemas import RunDetail, RunPage
from fdh.controlplane.catalog import CatalogQueries


def run_routes(queries: CatalogQueries) -> APIRouter:
    router = APIRouter(prefix="/api/v1/runs")

    @router.get("", operation_id="listRuns", responses=COLLECTION)
    async def runs(
        source_id: SourceId | None = None, page: Page = 1, page_size: Size = 20
    ) -> RunPage:
        return RunPage.model_validate(await queries.runs(page, page_size, source_id or ""))

    @router.get("/{runId}", operation_id="getRun", responses=RESOURCE)
    async def detail(run_id: Annotated[UUID, Path(alias="runId")]) -> RunDetail:
        return RunDetail.model_validate(await queries.run(run_id))

    return router
