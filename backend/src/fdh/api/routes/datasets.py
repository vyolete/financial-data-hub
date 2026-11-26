"""Dataset and facet routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path

from fdh.api.routes.parameters import COLLECTION, RESOURCE, Page, Size, Text
from fdh.api.schemas import DatasetDetail, DatasetPage, ObservationPage, ValuePage
from fdh.controlplane.catalog import CatalogQueries


def dataset_routes(queries: CatalogQueries) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/datasets", operation_id="searchDatasets", responses=COLLECTION)
    async def datasets(
        q: Text | None = None,
        provider: Text | None = None,
        category: Text | None = None,
        page: Page = 1,
        page_size: Size = 20,
    ) -> DatasetPage:
        return DatasetPage.model_validate(
            await queries.datasets(
                page, page_size, (q or "").strip(), provider or "", category or ""
            )
        )

    @router.get("/datasets/{datasetId}", operation_id="getDataset", responses=RESOURCE)
    async def detail(dataset_id: Annotated[UUID, Path(alias="datasetId")]) -> DatasetDetail:
        return DatasetDetail.model_validate(await queries.dataset(dataset_id))

    @router.get(
        "/datasets/{datasetId}/provenance", operation_id="listDatasetProvenance", responses=RESOURCE
    )
    async def provenance(
        dataset_id: Annotated[UUID, Path(alias="datasetId")],
        page: Page = 1,
        page_size: Size = 20,
    ) -> ObservationPage:
        return ObservationPage.model_validate(await queries.provenance(dataset_id, page, page_size))

    @router.get("/providers", operation_id="listProviders", responses=COLLECTION)
    async def providers(page: Page = 1, page_size: Size = 20) -> ValuePage:
        return ValuePage.model_validate(await queries.providers(page, page_size))

    @router.get("/categories", operation_id="listCategories", responses=COLLECTION)
    async def categories(q: Text | None = None, page: Page = 1, page_size: Size = 20) -> ValuePage:
        return ValuePage.model_validate(
            await queries.categories(page, page_size, (q or "").strip())
        )

    return router
