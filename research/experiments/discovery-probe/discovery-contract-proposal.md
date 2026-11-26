# Propuesta de contrato común de descubrimiento

**Estado**: propuesta, no aprobada. Insumo para `speckit-plan` de FDH-001 (FR-01 a FR-03, FR-06, NFR-01, NFR-02; AC-30 a AC-36). Se basa en la evidencia de [Socrata](../../sources/colombia/socrata/README.md) y [World Bank](../../sources/international/world-bank/README.md). No se ha implementado ni probado contra un adaptador.

## Reparto de responsabilidades

| Núcleo del catálogo | Adaptador (uno por plataforma) |
|---|---|
| Configuración de fuentes y registro de adaptadores | Validar sus opciones y consultas |
| Bucle de páginas y límite `max_pages` | Construir la solicitud de una página |
| Tiempo por intento, reintentos, `Retry-After` y pausas | Clasificar errores propios de la plataforma, incluidos los que llegan como 200 |
| Deduplicación, persistencia, procedencia y estado de la ejecución | Traducir la respuesta a registros comunes y rechazar los inválidos |
| `source_id`, `provider`, `platform`, atribución, estado de revisión y permisos (desde configuración o comando local) | Nada de esto |
| Rechazar configuraciones que exijan capacidades no declaradas | Declarar sus capacidades |

Añadir una plataforma consiste en escribir un adaptador, registrarlo y configurar una fuente, sin cambiar el núcleo. El adaptador no accede a la red ni a la base de datos.

## Tipos

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional, Protocol, Tuple


class Permission(Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    UNDETERMINED = "undetermined"


@dataclass(frozen=True)
class AdapterCapabilities:
    text_search: bool
    declares_total: bool                # the platform reports the number of matches
    cursor_pagination: bool
    supported_filters: Tuple[str, ...]
    max_page_size: Optional[int]        # None: not established


@dataclass(frozen=True)
class DiscoveryQuery:
    term: Optional[str] = None
    filters: Optional[Mapping[str, str]] = None     # platform specific


@dataclass(frozen=True)
class SourceConfig:
    source_id: str                      # stable, e.g. "co-datos-gov"
    provider: str
    platform: str                       # adapter registry key: "socrata", "data360"
    official_url: str
    allowed_hosts: Tuple[str, ...]
    queries: Tuple[DiscoveryQuery, ...]
    page_size: int = 100
    max_pages: int = 5                  # per query
    attempt_timeout_s: float = 10.0     # deadline of each attempt
    max_retries: int = 3                # additional to the first attempt
    max_retry_after_s: int = 60
    metadata_publication: Permission = Permission.UNDETERMINED
    attribution: Optional[str] = None
    options: Optional[Mapping[str, str]] = None     # validated by the adapter


@dataclass(frozen=True)
class DatasetDates:
    created_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    metadata_updated_at: Optional[datetime] = None
    data_updated_at: Optional[datetime] = None


@dataclass(frozen=True)
class AccessLocator:
    kind: str                           # open vocabulary: "web", "api", "json", "csv", ...
    url: str                            # declared by the source, not fetched by discovery
    source_field: str                   # where the source declared it


@dataclass(frozen=True)
class DeclaredLicense:
    name: Optional[str]                 # verbatim, never a permission
    url: Optional[str] = None
    note: Optional[str] = None


@dataclass(frozen=True)
class DiscoveredDataset:
    external_id: str
    title: str
    description: Optional[str]
    publisher: Optional[str]
    original_categories: Tuple[str, ...]            # verbatim
    original_topics: Tuple[str, ...]                # verbatim
    tags: Tuple[str, ...]
    official_url: Optional[str]
    declared_licenses: Tuple[DeclaredLicense, ...]
    citation_requirement: Optional[str]
    dates: DatasetDates
    access_locators: Tuple[AccessLocator, ...]


@dataclass(frozen=True)
class RejectedRecord:
    external_id: Optional[str]
    reason: str                         # sanitized code, no payload


@dataclass(frozen=True)
class DiscoveryPage:
    datasets: Tuple[DiscoveredDataset, ...]
    rejected: Tuple[RejectedRecord, ...]
    total_matches: Optional[int]
    next_cursor: Optional[str]          # opaque; None means no more pages


class ErrorKind(Enum):
    TRANSIENT = "transient"             # the core may retry
    PERMANENT = "permanent"
    INVALID_RESPONSE = "invalid_response"


@dataclass(frozen=True)
class HttpRequest:
    method: str                         # "GET" or "POST"; discovery requests are read only
    url: str
    params: Optional[Mapping[str, str]] = None
    json_body: Optional[Mapping[str, Any]] = None


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class RunStatus(Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


def final_status(valid: int, rejected: int, failures: int) -> RunStatus:
    """Outcome of a finished run. Truncation is not an input: it is not an error."""
    if rejected == 0 and failures == 0:
        return RunStatus.SUCCEEDED
    return RunStatus.PARTIAL if valid > 0 else RunStatus.FAILED


class DiscoveryAdapter(Protocol):
    platform: str
    capabilities: AdapterCapabilities

    def validate(self, source: SourceConfig) -> None: ...

    def build_request(self, source: SourceConfig, query: DiscoveryQuery,
                      cursor: Optional[str]) -> HttpRequest: ...

    def classify(self, response: HttpResponse) -> Optional[ErrorKind]: ...

    def parse(self, source: SourceConfig, request: HttpRequest,
              response: HttpResponse) -> DiscoveryPage: ...
```

El núcleo ejecuta `HttpRequest`. Así la política de reintentos es única y las pruebas usan respuestas sintéticas sin red. Un `POST` de búsqueda puede reintentarse porque no modifica datos.

## Reglas
1. La identidad es (`source_id`, `external_id`); el núcleo deduplica dentro de la ejecución y entre ejecuciones.
2. La paginación por desplazamiento no garantiza completitud. El núcleo cuenta recibidos y distintos.
3. Si quedan resultados al alcanzar `max_pages`, el núcleo registra por consulta `truncated` y `total_matches` si la plataforma lo declara.
4. El estado final sigue `final_status`: sin fallos ni rechazos es `succeeded`, aunque esté vacío; con ellos es `partial` si hubo algún registro válido y `failed` si no.
5. Cada intento tiene su propio plazo; hay como máximo `max_retries` reintentos y ninguno si `Retry-After` supera `max_retry_after_s`.
6. Un campo ausente es `None` o una colección vacía; el adaptador no infiere valores.
7. El adaptador descarta nombres de propietarios, creadores y contactos.
8. Toda respuesta se valida: estado 200 no implica éxito.
9. `validate` rechaza opciones desconocidas o capacidades no soportadas antes de la primera solicitud.
10. Las solicitudes solo van a `allowed_hosts`. El núcleo guarda cada localizador como `unverified`, o `invalid` si no es una URL HTTPS bien formada; no los consulta.
11. `metadata_publication` no concede extracción ni redistribución; esos permisos son de cada dataset y los administra el núcleo.
12. Un conjunto de pruebas de contrato se ejecuta contra cada adaptador, sin red ni base de datos.

## Capacidades observadas

| Capacidad | Socrata | Data360 |
|---|---|---|
| `text_search` | sí (`q`) | sí (`search`) |
| `declares_total` | sí (`resultSetSize`) | sí, con `count: true` (`@odata.count`) |
| `cursor_pagination` | sí (`scroll_id`, incompatible con `order`) | no observada; usa `skip` hasta 100000 |
| `max_page_size` | no establecido | no establecido |

## Correspondencia preliminar

| Campo | Socrata (observado) | Data360 (observado) |
|---|---|---|
| `external_id` | `resource.id` | `idno` |
| `title` | `resource.name` | `series_description.name` |
| `description` | `resource.description` | `series_description.definition_long` |
| `publisher` | `resource.attribution` | por decidir; `authoring_entity` vacío |
| `original_categories` | `classification.domain_category` | no observado |
| `original_topics` | no observado | `series_description.topics[].name` |
| `tags` | `classification.domain_tags` | `tags[].tag` |
| `official_url` | `permalink` | por decidir: `links[]` o `api_explorer_link` |
| `declared_licenses` | `metadata.license` | `series_description.license[]`: `name`, `uri`, `note` |
| `citation_requirement` | no observado; la cita es de la fuente | `series_description.citation_requirement` |
| `dates` | `resource.*` | `series_description.date_last_update` |
| `access_locators` | `permalink`, `link` | `api_link`, `csv_link`, `json_link` |
| Solicitud | `GET` | `POST` con cuerpo JSON |
| `next_cursor` | `offset` o `scroll_id` | siguiente `skip` |
| Búsqueda por texto | `q` | `search` |
| Errores observados | 400, 404, 500 | 400 |

Ambas colecciones admiten cero o varios valores. El filtro por categoría de la API coincide con cualquiera de las dos. `classification.categories` de Socrata llegó vacío en las pruebas.

## Relación con el futuro contrato de extracción (FDH-002 y FDH-003)

Boceto para no cerrar puertas; no forma parte de FDH-001.

| Aspecto | Descubrimiento | Extracción |
|---|---|---|
| Pregunta | Qué datasets existen | Qué datos y cambios entrega un dataset |
| Entrada | Fuente y consultas | `DatasetRef`, localizadores y estado de sincronización |
| Salida | Metadatos | Esquema, lotes de registros y estado nuevo |
| Destino | Catálogo (plano de control) | Bronze (plano de datos) |
| Estado | Historial de ejecuciones | Cursores incrementales |

```python
from typing import Iterator


@dataclass(frozen=True)
class DatasetRef:
    source_id: str
    external_id: str


class ExtractionConnector(Protocol):
    def describe(self, ref: DatasetRef,
                 locators: Tuple[AccessLocator, ...]) -> "DatasetSchema": ...

    def extract(self, ref: DatasetRef,
                state: Optional["SyncState"]) -> Iterator["RecordBatch"]: ...
```

- Comparten registro de fuentes, identidad, política de red, atribución y condiciones de uso.
- Los contratos son independientes: un adaptador de descubrimiento no está obligado a extraer.
- World Bank Indicators API es candidata para este contrato. En una [evidencia revisada pero no reproducida](../../sources/international/world-bank/README.md), 3581 códigos aparecieron en más de una fuente estadística: su identidad externa tendría que combinar fuente e indicador.
- El estado y los cursores pertenecen al plano de control.
- Que dlt pueda implementar `ExtractionConnector` es una **hipótesis** por comprobar en las pruebas de concepto de [ADR-0007](../../../docs/adr/0007-integration-and-orchestration.md).
- Un localizador declarado no garantiza acceso ni permiso para extraer.

## Cuestiones para el plan
- Cursor u `offset` en Socrata: el cursor recorrió 145 distintos; `offset` repitió un registro en una de las ejecuciones, y el cursor no admite `order`.
- Socrata respondió 500 a parámetros inválidos: validar antes de enviar.
- Cómo imponer un plazo total a cada intento; el tiempo de espera de la biblioteca usada en las pruebas aplica a cada operación de red.
- Si una ejecución con varias consultas se detiene tras un fallo o continúa con las demás.
- URL oficial y publicador en Data360.
