"""Read-side errors shared by storage and HTTP."""

from typing import Any, Protocol
from uuid import UUID

Record = dict[str, Any]


class StorageUnavailable(Exception):
    """The catalog could not be read."""


class ResourceNotFound(Exception):
    """The resource is missing or unavailable for publication."""


class CatalogQueries(Protocol):
    async def datasets(
        self, page: int, size: int, q: str, provider: str, category: str
    ) -> Record: ...
    async def dataset(self, id: UUID) -> Record: ...
    async def provenance(self, id: UUID, page: int, size: int) -> Record: ...
    async def providers(self, page: int, size: int) -> Record: ...
    async def categories(self, page: int, size: int, q: str) -> Record: ...
    async def runs(self, page: int, size: int, source_id: str) -> Record: ...
    async def run(self, id: UUID) -> Record: ...
