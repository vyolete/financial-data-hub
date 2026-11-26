# Contrato de configuración de fuentes

Archivo `config/sources.toml`, versionado y sin secretos. Se localiza con `--config` o la variable `FDH_CONFIG`. En Compose, el directorio `config/` se monta en solo lectura únicamente en los servicios del backend; no se copia en la imagen. Requisitos: FR-01, FR-06, NFR-01, NFR-02.

```toml
[defaults]
page_size = 100
max_pages = 5                 # per query
attempt_timeout_s = 10.0
max_retries = 3               # additional to the first attempt
max_retry_after_s = 60

[[sources]]
source_id = "co-datos-gov"
provider = "MinTIC"
platform = "socrata"
base_url = "https://api.us.socrata.com/api/catalog/v1"
allowed_hosts = ["api.us.socrata.com"]
official_url = "https://www.datos.gov.co"
verified_at = 2026-11-26
attribution = "Fuente: Portal de Datos Abiertos www.datos.gov.co"
access_conditions = "Consulta pública sin autenticación observada en las pruebas"
redistribution_conditions = "Los términos del portal permiten redistribuir citando la fuente; la licencia se declara por dataset"
# license_name and license_url omitted: no single licence for the source, it is declared per dataset
terms_url = "https://herramientas.datos.gov.co/terminos"
terms_checked_on = 2026-11-26

[sources.metadata_publication]
value = "allowed"
declared_by = "maintainer"
declared_on = 2026-11-25
evidence = "https://github.com/vyolete/financial-data-hub/issues/2#issuecomment-7179859703"

[sources.options]
domains = "www.datos.gov.co"

[[sources.queries]]
term = "presupuesto"

[[sources.queries]]
term = "finanzas"

[[sources]]
source_id = "int-worldbank-data360"
provider = "World Bank"
platform = "data360"
base_url = "https://data360api.worldbank.org/data360/searchv2"
allowed_hosts = ["data360api.worldbank.org"]
official_url = "https://data360.worldbank.org"
verified_at = 2026-11-26
attribution = "The World Bank"
access_conditions = "API pública sin autenticación observada en las pruebas"
redistribution_conditions = "CC BY 4.0 salvo indicación; algunos datasets declaran licencias externas, restrictivas o ninguna"
license_name = "CC BY 4.0 salvo indicación en cada dataset"
license_url = "https://datacatalog.worldbank.org/public-licenses"
terms_url = "https://www.worldbank.org/ext/en/legal/terms-conditions/datasets"
terms_checked_on = 2026-11-26

[sources.metadata_publication]
value = "allowed"
declared_by = "maintainer"
declared_on = 2026-11-25
evidence = "https://github.com/vyolete/financial-data-hub/issues/2#issuecomment-7179859703"

[[sources.queries]]
term = "finance"
```

## Validación

| Regla | Efecto si falla |
|---|---|
| `source_id` único, `^[a-z0-9-]+$` | El comando termina sin solicitudes |
| `platform` conocida; con adaptador registrado, `options` y consultas compatibles con sus capacidades | `discover` termina sin solicitudes; `config check` y `sources sync` informan si el adaptador no está disponible |
| `base_url` HTTPS y su host en `allowed_hosts` | Igual |
| `1 ≤ page_size ≤ 100`, `1 ≤ max_pages ≤ 100`, `attempt_timeout_s > 0`, `0 ≤ max_retries ≤ 3`, `max_retry_after_s ≥ 0` | Igual |
| `official_url`, `license_url` y `terms_url` HTTPS si se indican | Igual |
| `value` distinto de `undetermined` exige `declared_by`, `declared_on` y `evidence` | Igual |
| Claves desconocidas | Igual |

- Una fuente sin `metadata_publication` queda `undetermined`: se puede descubrir, pero sus datasets no se muestran.
- Los límites de `[defaults]` pueden redefinirse por fuente.
- Licencia, condiciones y su fecha de revisión omitidas significan desconocido y no conceden permisos.
- `fdh sources sync` aplica los cambios sin red; cambiar el permiso de publicación registra una entrada en la bitácora.
- Una fuente retirada del archivo pasa a `undetermined` al sincronizar.
- Los términos de búsqueda son la configuración inicial y pueden cambiarse sin modificar código (AC-02). `presupuesto` y `finance` se probaron en vivo; `finanzas`, no.
