# Modelo de datos

PostgreSQL 18. Identificadores `uuid` salvo indicación; marcas temporales `timestamptz` en UTC. Un valor desconocido es `NULL` o un arreglo vacío; nunca se infiere.

## Enumeraciones

| Nombre | Valores |
|---|---|
| `permission` | `allowed`, `denied`, `undetermined` |
| `review_status` | `pending`, `verified`, `restricted` |
| `run_status` | `running`, `succeeded`, `partial`, `failed` |
| `locator_status` | `unverified`, `invalid` |

## `sources`
Se sincroniza desde `config/sources.toml`.

| Columna | Tipo | Notas |
|---|---|---|
| `source_id` | text PK | Estable, por ejemplo `co-datos-gov` |
| `provider`, `platform` | text | Obligatorios |
| `official_url` | text | HTTPS |
| `verified_at` | date | Fecha de verificación de la fuente |
| `access_conditions`, `redistribution_conditions` | text null | Por separado; resumen de lo consultado, nunca un permiso |
| `license_name`, `license_url` | text null | Licencia declarada para la fuente; desconocida si se omite. No sustituye la de cada dataset |
| `terms_url`, `terms_checked_on` | text null, date null | Condiciones de uso consultadas |
| `metadata_publication` | permission | `undetermined` por defecto |
| `publication_evidence_url`, `publication_declared_by`, `publication_declared_on` | text, text, date | Obligatorios si no es `undetermined` |
| `attribution_text` | text null | |

## `datasets`

| Columna | Tipo | Notas |
|---|---|---|
| `id` | uuid PK | |
| `source_id` | text FK | |
| `external_id` | text | Único con `source_id` |
| `title` | text | Obligatorio |
| `description`, `publisher`, `official_url` | text null | |
| `categories`, `topics`, `tags` | text[] | Originales, textuales |
| `category_keys` | text[] | `casefold` de categorías y temas; índice GIN |
| `data_sources` | text[] | Organizaciones declaradas, para la atribución |
| `licenses` | jsonb | Lista de `{name, url, note}`; vacía si no se declara |
| `citation_requirement` | text null | |
| `created_at_source`, `published_at_source`, `metadata_updated_at_source`, `data_updated_at_source`, `updated_at_source` | timestamptz null | Último: fecha sin significado precisado |
| `access_conditions`, `redistribution_conditions` | text null | Registradas por una persona |
| `review_status` | review_status | `pending` por defecto |
| `extraction_permission`, `redistribution_permission` | permission | `undetermined` por defecto |
| `first_seen_at`, `last_seen_at` | timestamptz | |
| `first_seen_run_id`, `last_seen_run_id` | uuid FK | |
| `metadata_hash` | text | Detecta cambios |

El redescubrimiento **no modifica** `review_status`, permisos ni condiciones registradas por una persona. Un dataset ausente no se elimina.

## `access_locators`

| Columna | Tipo | Notas |
|---|---|---|
| `id` | uuid PK | |
| `dataset_id` | uuid FK | |
| `kind` | text | Vocabulario abierto |
| `url` | text | Tal como se declaró |
| `source_field` | text | Campo de origen |
| `status` | locator_status | `invalid` si no es una URL HTTPS absoluta con host |

Único por (`dataset_id`, `kind`, `url`, `source_field`). Cada observación reemplaza el conjunto por el declarado y vuelve a validarlo. Un localizador es utilizable para extracción solo si no es `invalid`; la extracción exige además permiso `allowed` y queda fuera de FDH-001.

## `runs`

| Columna | Tipo | Notas |
|---|---|---|
| `id` | uuid PK | |
| `source_id` | text FK | |
| `status` | run_status | |
| `parameters` | jsonb | Consultas y límites, sin secretos |
| `started_at`, `finished_at` | timestamptz | `finished_at` nulo mientras está `running` |
| `pages_processed`, `received`, `created`, `updated`, `unchanged`, `rejected`, `failures` | integer | |
| `errors` | jsonb | `{code, message, query_index, http_status, attempts}` sanitizados |

`received` cuenta todos los registros recibidos, repetidos incluidos. `created`, `updated` y `unchanged` cuentan datasets distintos, una sola vez por ejecución según su primera aparición: nuevo, con metadatos distintos o iguales. Las repeticiones solo suman en `received` y como observaciones. `rejected` cuenta registros rechazados.

## `run_queries`

| Columna | Tipo | Notas |
|---|---|---|
| `run_id`, `query_index` | uuid, integer | PK |
| `term` | text null | |
| `filters` | jsonb | |
| `pages_processed` | integer | |
| `total_declared` | integer null | |
| `truncated` | boolean | |

## `dataset_observations`
Procedencia e historial de búsquedas.

| Columna | Tipo | Notas |
|---|---|---|
| `id` | bigint PK | |
| `dataset_id`, `run_id` | uuid FK | |
| `query_index` | integer | |
| `source_url` | text | URL de la solicitud, sin secretos |
| `request_summary` | jsonb | Parámetros o cuerpo de la búsqueda |
| `observed_at` | timestamptz | |

Único por (`dataset_id`, `run_id`, `query_index`).

## `permission_decisions`
Bitácora de cambios hechos por una persona. Solo inserción.

| Columna | Tipo |
|---|---|
| `id` | bigint PK |
| `source_id` | text FK |
| `dataset_id` | uuid FK null |
| `field`, `old_value`, `new_value` | text |
| `evidence`, `decided_by` | text, obligatorios |
| `decided_at`, `recorded_at` | timestamptz |

## Estados de una ejecución

```text
running ──► succeeded   rejected = 0 y failures = 0 (aunque valid = 0)
        ──► partial     hay rechazos o fallos y valid > 0
        ──► failed      hay rechazos o fallos y valid = 0
```

`truncated` no interviene. Una ejecución abandonada se cierra con un fallo `interrupted`.

## Sincronización de fuentes y revocación

`fdh sources sync` aplica `sources.toml` usando solo la base de datos, sin solicitudes externas; `discover` la ejecuta antes de empezar.

- Cambiar `metadata_publication` surte efecto al sincronizar y se anota en la bitácora.
- Una fuente retirada de la configuración conserva sus datos y pasa a `undetermined`; la bitácora la anota con el actor `fdh sources sync`.
- Cualquier otro cambio de permiso exige persona, fecha y evidencia.
- La sincronización nunca modifica el estado de revisión, los permisos ni las condiciones de un dataset.

## Correspondencia de fechas

| Columna | Contrato de adaptador y API |
|---|---|
| `created_at_source` | `created_at` |
| `published_at_source` | `published_at` |
| `metadata_updated_at_source` | `metadata_updated_at` |
| `data_updated_at_source` | `data_updated_at` |
| `updated_at_source` | `updated_at` |

## Visibilidad en la API

Un dataset es visible si `sources.metadata_publication = 'allowed'` **y** `datasets.review_status <> 'restricted'`. La regla vive en un único punto del repositorio y se aplica a búsqueda, detalle, procedencia, proveedores y categorías. Las ejecuciones son visibles siempre: no contienen metadatos de datasets.

## Índices

Único (`source_id`, `external_id`); GIN en `category_keys`; (`source_id`, `review_status`); `runs` (`source_id`, `started_at desc`); `dataset_observations` (`dataset_id`, `observed_at desc`). La búsqueda por texto usa `unaccent` e `ILIKE` con comodines escapados.
