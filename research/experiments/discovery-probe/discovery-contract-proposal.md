# Propuesta de contrato común de descubrimiento

**Estado**: propuesta, no aprobada. Insumo para `speckit-plan` de FDH-001 (FR-01 a FR-03, FR-06, NFR-01, NFR-02). Se basa en la evidencia de [Socrata](../../sources/colombia/socrata/README.md) y [World Bank](../../sources/international/world-bank/README.md). No se ha implementado ni probado.

## Reparto de responsabilidades

| Núcleo del catálogo | Adaptador (uno por plataforma) |
|---|---|
| Configuración de fuentes y registro de adaptadores | Validar sus opciones y consultas |
| Bucle de páginas y límite `max_pages` | Construir la solicitud de una página |
| Tiempo de espera, reintentos, `Retry-After` y pausas | Clasificar errores propios de la plataforma, incluidos los que llegan como 200 |
| Deduplicación, persistencia, procedencia y estado de la ejecución | Traducir la respuesta a registros comunes y rechazar los inválidos |
| `source_id`, `provider`, `platform`, estado de revisión y permisos (desde la fuente) | Nada de esto |

Añadir una plataforma consiste en escribir un adaptador, registrarlo y configurar una fuente, sin cambiar el núcleo. El adaptador no accede a la base de datos.

## Tipos

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Mapping, Optional, Protocol, Tuple


@dataclass(frozen=True)
class SourceConfig:
    source_id: str                  # stable, e.g. "co-datos-gov"
    provider: str
    platform: str                   # adapter registry key, e.g. "socrata"
    official_url: str
    allowed_hosts: Tuple[str, ...]
    queries: Tuple["DiscoveryQuery", ...]
    page_size: int = 100
    max_pages: int = 5
    options: Optional[Mapping[str, str]] = None   # validated by the adapter


@dataclass(frozen=True)
class DiscoveryQuery:
    term: Optional[str] = None
    filters: Optional[Mapping[str, str]] = None   # platform specific


@dataclass(frozen=True)
class DatasetDates:
    created_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    metadata_updated_at: Optional[datetime] = None
    data_updated_at: Optional[datetime] = None


@dataclass(frozen=True)
class DiscoveredDataset:
    external_id: str
    title: str
    description: Optional[str]
    publisher: Optional[str]
    original_category: Optional[str]    # verbatim
    tags: Tuple[str, ...]
    official_url: Optional[str]
    declared_license: Optional[str]     # verbatim, never a permission
    dates: DatasetDates


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
    url: str
    params: Mapping[str, str]


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class DiscoveryAdapter(Protocol):
    platform: str
    supports_text_search: bool

    def validate(self, source: SourceConfig) -> None: ...

    def build_request(self, source: SourceConfig, query: DiscoveryQuery,
                      cursor: Optional[str]) -> HttpRequest: ...

    def classify(self, response: HttpResponse) -> Optional[ErrorKind]: ...

    def parse(self, source: SourceConfig, request: HttpRequest,
              response: HttpResponse) -> DiscoveryPage: ...
```

El adaptador no realiza llamadas de red: el núcleo ejecuta `HttpRequest`. Así la política de reintentos es única y las pruebas usan respuestas sintéticas sin red.

## Reglas
1. La identidad es (`source_id`, `external_id`); el núcleo deduplica dentro de la ejecución y entre ejecuciones.
2. La paginación por desplazamiento no garantiza completitud (se observó un registro repetido entre páginas). El núcleo cuenta recibidos y distintos.
3. Si quedan resultados al alcanzar `max_pages`, la ejecución registra `total_matches` y `truncated`.
4. Un campo ausente es `None`; el adaptador no infiere valores.
5. El adaptador descarta nombres de propietarios, creadores y contactos.
6. Toda respuesta se valida: estado 200 no implica éxito.
7. `validate` rechaza opciones desconocidas antes de la primera solicitud; una consulta con texto falla si `supports_text_search` es falso.
8. La URL de la solicitud solo puede apuntar a `allowed_hosts`.
9. Un conjunto de pruebas de contrato se ejecuta contra cada adaptador.

## Correspondencia preliminar

| Campo | Socrata (observado) | World Bank Indicators (opción A, sin aprobar) |
|---|---|---|
| `external_id` | `resource.id` | `id` |
| `title` | `resource.name` | `name` |
| `description` | `resource.description` | `sourceNote` |
| `publisher` | `resource.attribution` | por decidir; `sourceOrganization` es texto libre |
| `original_category` | `classification.domain_category` | por decidir; `topics[]` admite varios |
| `tags` | `classification.domain_tags` | vacío |
| `official_url` | `permalink` | no viene en la respuesta |
| `declared_license` | `metadata.license` | no viene en la respuesta |
| `dates` | `resource.*` | no vienen por indicador |
| `next_cursor` | siguiente `offset` | siguiente `page` |
| Búsqueda por texto | `q` | no disponible en las pruebas |
| Error en 200 | no observado | objeto `message` |

## Cuestiones para el plan
- ¿El límite de 10 s es total o por operación de red? Una solicitud de 100 registros tardó 11,7 s. Propuesta: límite total configurable y medirlo antes de ajustar el valor o el tamaño de página.
- Socrata respondió 500 a parámetros inválidos: se reintentará hasta el máximo. Mitigación: validar parámetros antes de enviar.
- `max_pages` rige por consulta y fuente; definir si una ejecución agrupa varias consultas.
- Un `original_category` único no representa varios temas.
