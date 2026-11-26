# Investigación de FDH-001

Pruebas en vivo ejecutadas el 2026-11-26 (UTC). Los detalles y la evidencia viven en `research/`.

| Tema | Resultado | Evidencia |
|---|---|---|
| Socrata Discovery API, `www.datos.gov.co` | Accesible; paginación, errores y metadatos observados. Referencia oficial de la API sin revisar | [informe](../../research/sources/colombia/socrata/README.md) |
| World Bank Data Catalog API | No utilizable en las pruebas: HTTP 429 persistente | [informe](../../research/sources/international/world-bank/README.md) |
| World Bank Indicators API | Accesible; no equivale a un catálogo de datasets | [informe](../../research/sources/international/world-bank/README.md) |
| Contrato común de descubrimiento | Propuesta sin aprobar | [propuesta](../../research/experiments/discovery-probe/discovery-contract-proposal.md) |

## Pendiente
- Revisión humana de condiciones de uso y declaración del permiso de publicación de metadatos de cada fuente (NFR-02). Hasta entonces ambas siguen `undetermined`.
- Aprobación de la alternativa para World Bank (FR-06, AC-20).
- Decidir si el límite de 10 s es total y qué hacer con respuestas lentas (NFR-01, AC-22).
- Decidir cómo informar resultados truncados por el máximo de páginas.
- **LAB-01**: un informe anterior registró cero datasets en Socrata. Las pruebas actuales obtuvieron resultados; la causa del informe anterior sigue sin determinar.
