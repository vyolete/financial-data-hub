# Inventario de fuentes

Registro central de las fuentes candidatas aprobadas por la mantenedora el 2026-11-25. Ser candidata no significa que su API, licencia o redistribución estén verificadas. Orden y etapas de integración: [roadmap](../../ROADMAP.md).

## Estados

| Campo | Valores |
|---|---|
| Validación | `no investigada`; `probada en vivo` (con evidencia en este directorio) |
| Publicación de metadatos | `undetermined` (predeterminado), `allowed`, `denied` |
| Revisión de cada dataset | `pending` (predeterminado), `verified`, `restricted`; se registra en el catálogo, no aquí |
| Extracción y redistribución de datos | Por dataset: `undetermined` (predeterminado), `allowed`, `denied`; independientes entre sí y de la publicación de metadatos |

«Hipótesis» marca una suposición por verificar; no debe usarse para implementar.

## Identificación

| ID | Grupo | Proveedor | Plataforma | Protocolo | Dataset |
|---|---|---|---|---|---|
| `co-datos-gov` | Colombia | MinTIC (Datos Abiertos Colombia) | Socrata | REST/JSON, Discovery API | 8475 datasets en el catálogo el 2026-11-26 |
| `co-banrep` | Colombia | Banco de la República | por verificar | por verificar | por identificar |
| `co-superfinanciera` | Colombia | Superintendencia Financiera de Colombia | por verificar | por verificar | por identificar |
| `co-supersociedades` | Colombia | Superintendencia de Sociedades | por verificar | por verificar | por identificar |
| `co-dane` | Colombia | DANE | por verificar | por verificar | por identificar |
| `int-worldbank-data360` | Internacional | World Bank | Data360 | REST/JSON, `POST` de búsqueda | 174 entradas `dataset` el 2026-11-26 |
| `int-fred` | Internacional | Federal Reserve Bank of St. Louis (hipótesis) | FRED | por verificar (hipótesis: REST con clave) | por identificar |
| `int-imf` | Internacional | IMF | por verificar | por verificar (hipótesis: SDMX) | por identificar |
| `int-oecd` | Internacional | OECD | por verificar | por verificar (hipótesis: SDMX) | por identificar |
| `int-sec-edgar` | Internacional | U.S. SEC (hipótesis) | EDGAR | por verificar (hipótesis: REST y archivos) | por identificar |
| `mkt-coingecko` | Mercados | CoinGecko | por verificar | por verificar (hipótesis: REST) | por identificar |
| `mkt-yahoo-finance` | Mercados | Yahoo | Yahoo Finance | por verificar (hipótesis: sin API pública oficial) | por identificar |

## Validación y condiciones de uso

| ID | Validación | Condiciones de uso | Publicación de metadatos | Evidencia | Alcance |
|---|---|---|---|---|---|
| `co-datos-gov` | probada en vivo | Términos del portal: permiten redistribución con cita; licencia por dataset | `allowed` | [informe](colombia/socrata/README.md) | FDH-001 |
| `co-banrep` | no investigada | sin verificar | `undetermined` | ninguna | posterior |
| `co-superfinanciera` | no investigada | sin verificar | `undetermined` | ninguna | posterior |
| `co-supersociedades` | no investigada | sin verificar | `undetermined` | ninguna | posterior |
| `co-dane` | no investigada | sin verificar para integración | `undetermined` | ninguna | posterior |
| `int-worldbank-data360` | probada en vivo | CC BY 4.0 salvo indicación; licencias por dataset heterogéneas o externas | `allowed` | [informe](international/world-bank/README.md) | FDH-001 |
| `int-fred` | no investigada | sin verificar | `undetermined` | ninguna | posterior |
| `int-imf` | no investigada | sin verificar | `undetermined` | ninguna | posterior |
| `int-oecd` | no investigada | sin verificar | `undetermined` | ninguna | posterior |
| `int-sec-edgar` | no investigada | sin verificar | `undetermined` | ninguna | posterior |
| `mkt-coingecko` | no investigada | sin verificar | `undetermined` | ninguna | posterior |
| `mkt-yahoo-finance` | no investigada | sin verificar; riesgo de condiciones restrictivas (hipótesis) | `undetermined` | ninguna | posterior |

## Declaraciones de publicación

| Fuente | Declaración | Atribución obligatoria | Base consultada |
|---|---|---|---|
| `co-datos-gov` | `allowed` para metadatos | «Fuente: Portal de Datos Abiertos www.datos.gov.co» y fecha de última actualización cuando exista; sin alterar los metadatos de actualización ni las condiciones de uso | [Términos del portal](https://herramientas.datos.gov.co/terminos) |
| `int-worldbank-data360` | `allowed` para metadatos | The World Bank, nombre del dataset y fuente de los datos cuando se conozca; mostrar la licencia declarada | [Términos para datasets](https://www.worldbank.org/ext/en/legal/terms-conditions/datasets) |

- **Quién y cuándo**: la mantenedora, en sesión de trabajo del 2026-11-25. Recogidas en la especificación aprobada: [registro de aprobación](https://github.com/vyolete/financial-data-hub/issues/2#issuecomment-7179859703).
- **Alcance**: mostrar metadatos con atribución. No autoriza extraer ni redistribuir datos, que permanecen `undetermined` en todas las fuentes, ni marca datasets como `verified`.
- **Data360**: no todos sus datasets comparten condiciones; hay licencias externas, ausentes y restrictivas ([revisión](international/world-bank/README.md)).

## Otras API de fuentes ya listadas

No añaden fuentes a las 12 candidatas.

| Fuente | API | Situación | Uso previsto |
|---|---|---|---|
| World Bank | Indicators API v2 | probada en vivo ([informe](international/world-bank/README.md)) | Candidata para extraer indicadores y series económicas, FDH-002 y FDH-003 |

## Archivos

CSV, Excel y Parquet son formatos de entrada y salida, no fuentes: corresponden a la familia de conectores de archivos. Cada archivo concreto se registrará con su proveedor y condiciones.
