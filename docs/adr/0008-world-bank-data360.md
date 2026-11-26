# ADR-0008: Data360 como fuente de World Bank en FDH-001

- **Fecha**: 2026-11-25
- **Estado**: Accepted (registro verificable en GitHub pendiente)
- **Autoridad**: elegida por la mantenedora en sesión de trabajo del 2026-11-25. El registro
  verificable es un comentario personal suyo en el
  [issue #2](https://github.com/vyolete/financial-data-hub/issues/2); aún no consta.

## Contexto

FDH-001-FR-06 exige un segundo adaptador y aprobación si cambia la API prevista.

## Alternativas y evidencia

Ver el [informe de World Bank](../../research/sources/international/world-bank/README.md).

| Opción | Observado |
|---|---|
| Data360 | Sin autenticación; 174 datasets; búsqueda y paginación consistentes; beta |
| Indicators API | Accesible; 29544 indicadores; sin búsqueda por texto observada |
| Data Catalog API | HTTP 429 en las 22 solicitudes |

## Decisión

Usar `POST /data360/searchv2` con `type eq 'dataset'`. Un dataset de Data360 es un dataset del
catálogo, identificado por `idno`.

## Consecuencias

- El contrato de descubrimiento admite solicitudes `POST` de solo lectura.
- Las licencias son heterogéneas, y parte se declara externamente o no se declara.
- La condición beta obliga a validar cada respuesta y cubrir el adaptador con pruebas de contrato.
