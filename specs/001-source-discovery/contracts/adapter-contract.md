# Contrato de adaptadores de descubrimiento

Concreta la [propuesta de investigación](../../../research/experiments/discovery-probe/discovery-contract-proposal.md). Destino en código: `backend/src/fdh/domain/` y `backend/src/fdh/dataplane/connectors/contract.py`. Requisitos: FR-01 a FR-03, FR-06, NFR-01, NFR-02.

## Tipos

```python
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol


class ErrorKind(StrEnum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    INVALID_RESPONSE = "invalid_response"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


def final_status(valid: int, rejected: int, failures: int) -> RunStatus:
    """Outcome of a finished run. Truncation is not an input: it is not an error."""
    if rejected == 0 and failures == 0:
        return RunStatus.SUCCEEDED
    return RunStatus.PARTIAL if valid > 0 else RunStatus.FAILED


@dataclass(frozen=True)
class AdapterCapabilities:
    text_search: bool
    declares_total: bool
    cursor_pagination: bool
    supported_filters: tuple[str, ...] = ()
    max_page_size: int | None = None        # None: not established


@dataclass(frozen=True)
class DiscoveryQuery:
    term: str | None = None
    filters: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AdapterContext:
    """What an adapter may know about a source. Permissions are deliberately absent."""

    source_id: str
    base_url: str
    page_size: int
    options: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class HttpRequest:
    method: str                             # "GET" or "POST", read only
    url: str
    params: Mapping[str, str] = field(default_factory=dict)
    json_body: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


@dataclass(frozen=True)
class DatasetDates:
    created_at: datetime | None = None
    published_at: datetime | None = None
    metadata_updated_at: datetime | None = None
    data_updated_at: datetime | None = None
    updated_at: datetime | None = None      # declared without a precise meaning


@dataclass(frozen=True)
class AccessLocator:
    kind: str                               # open vocabulary
    url: str                                # verbatim; validity is decided by the core
    source_field: str


@dataclass(frozen=True)
class DeclaredLicense:
    name: str | None = None
    url: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class DiscoveredDataset:
    external_id: str
    title: str
    description: str | None = None
    publisher: str | None = None
    official_url: str | None = None
    categories: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    data_sources: tuple[str, ...] = ()
    licenses: tuple[DeclaredLicense, ...] = ()
    citation_requirement: str | None = None
    dates: DatasetDates = DatasetDates()
    locators: tuple[AccessLocator, ...] = ()


@dataclass(frozen=True)
class RejectedRecord:
    external_id: str | None
    reason: str     # "missing_id", "missing_title", "unexpected_type", "malformed"


@dataclass(frozen=True)
class DiscoveryPage:
    datasets: tuple[DiscoveredDataset, ...]
    rejected: tuple[RejectedRecord, ...]
    total_declared: int | None
    next_cursor: str | None                 # opaque; None means no more results


class InvalidResponse(Exception):
    """Raised by parse when the response as a whole cannot be interpreted."""


class DiscoveryAdapter(Protocol):
    platform: str
    capabilities: AdapterCapabilities

    def validate(self, context: AdapterContext,
                 queries: tuple[DiscoveryQuery, ...]) -> None: ...

    def build_request(self, context: AdapterContext, query: DiscoveryQuery,
                      cursor: str | None) -> HttpRequest: ...

    def classify(self, response: HttpResponse) -> ErrorKind | None: ...

    def parse(self, context: AdapterContext, request: HttpRequest,
              response: HttpResponse, cursor: str | None) -> DiscoveryPage: ...
```

## Obligaciones

| Parte | Obligación |
|---|---|
| Adaptador | Sin red, disco, base de datos ni reloj. Mismo resultado para la misma entrada |
| Adaptador | `validate` rechaza opciones desconocidas y capacidades no soportadas, antes de cualquier solicitud |
| Adaptador | `parse` no infiere: campo ausente es `None` o vacío. Un registro defectuoso va a `rejected` sin descartar los demás |
| Adaptador | Nunca devuelve nombres de propietarios, creadores ni contactos |
| Adaptador | `next_cursor` es `None` cuando la fuente no indica más resultados; el cursor lleva el conteo de vistos |
| Núcleo | Comprueba HTTPS y host permitido, aplica la política de red y reintentos |
| Núcleo | Valida localizadores, deduplica, persiste, asigna proveedor, plataforma, atribución y permisos |
| Núcleo | `classify` completa la clasificación por estado HTTP; no puede volver reintentable un 400, 401, 403 o 404 |

## Registro de adaptadores
`registry.py` asocia `platform` con una fábrica. Añadir una plataforma no modifica el motor, la persistencia, la API ni el portal (AC-21).

## Correspondencia de campos

| Campo | Socrata | Data360 |
|---|---|---|
| `external_id` | `resource.id` | `idno` |
| `title` | `resource.name` | `series_description.name` |
| `description` | `resource.description` | `series_description.definition_long` |
| `publisher` | `resource.attribution` | desconocido |
| `official_url` | `permalink` | desconocido |
| `categories` | `classification.domain_category` y `classification.categories` | vacío |
| `topics` | vacío | `series_description.topics[].name` |
| `tags` | `classification.domain_tags` y `classification.tags` | `tags[].tag` |
| `data_sources` | vacío | `series_description.sources[].organization` |
| `licenses` | `metadata.license` como `name` | `series_description.license[]`: `name`, `uri`, `note` |
| `citation_requirement` | vacío | `series_description.citation_requirement` |
| `dates` | `createdAt`, `publication_date`, `metadata_updated_at`, `data_updated_at` de `resource` | `series_description.date_last_update` como `updated_at` |
| `locators` | `permalink` y `link`, tipo `web` | `links[].uri` (`source_website`), `api_link` (`api`), `json_link`, `csv_link`, `api_explorer_link` (`api_explorer`) |

Los valores repetidos dentro de una colección se conservan una vez, en su orden.

## Cursores

| Adaptador | Primera solicitud | Siguiente |
|---|---|---|
| Socrata | `scroll_id` vacío | `scroll_id` = último identificador; fin si vistos ≥ total o página vacía |
| Data360 | `skip=0` | `skip` = vistos; fin si vistos ≥ total o página vacía; `skip` nunca supera 100000 |

## Suite de contrato
Cada adaptador pasa, con respuestas sintéticas identificadas y la red bloqueada:
primera página y continuación; última página; resultado vacío; total mayor que lo recibido; registro inválido junto a válidos; todos inválidos; respuesta que no es JSON; estado 200 con forma inesperada; clasificación de errores; opción desconocida; capacidad no soportada; ausencia de datos personales; correspondencia de todos los campos; localizador no HTTPS conservado.
