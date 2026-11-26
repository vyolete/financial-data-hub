# Investigación de FDH-001

Pruebas en vivo ejecutadas el 2026-11-26 (UTC). Los detalles y la evidencia viven en `research/`.

| Tema | Resultado | Evidencia |
|---|---|---|
| Socrata Discovery API, `www.datos.gov.co` | Accesible; paginación con `offset` y cursor, errores y metadatos observados. Referencia oficial de la API sin revisar | [informe](../../research/sources/colombia/socrata/README.md) |
| World Bank Data360 | Accesible; elegida para FR-06 ([ADR-0008](../../docs/adr/0008-world-bank-data360.md)) | [informe](../../research/sources/international/world-bank/README.md) |
| World Bank Data Catalog API | No utilizable en las pruebas: HTTP 429 persistente | [informe](../../research/sources/international/world-bank/README.md) |
| World Bank Indicators API | Accesible; candidata para extracción en FDH-002 y FDH-003. Su código de indicador no es único entre fuentes | [informe](../../research/sources/international/world-bank/README.md) |
| Contrato común de descubrimiento | Propuesta sin aprobar, con boceto de relación con la extracción | [propuesta](../../research/experiments/discovery-probe/discovery-contract-proposal.md) |
| Permisos de publicación | `allowed` declarado para ambas fuentes; registro en GitHub pendiente | [inventario](../../research/sources/inventory.md) |

## Pendiente para el plan
- Los cuatro puntos abiertos de la [especificación](spec.md).
- Cómo imponer el plazo de 10 segundos a cada intento: una solicitud de 100 registros en Socrata tardó 11,7 s.
- Revisión humana de las licencias externas y ausentes de Data360 antes de extraer datos.
- Leer la referencia oficial de Socrata Discovery API.
- **LAB-01**: un informe anterior registró cero datasets en Socrata. Las pruebas actuales obtuvieron resultados; la causa del informe anterior sigue sin determinar.
