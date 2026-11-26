# ADR-0003: Stack tecnológico base

- **Fecha**: 2026-11-25
- **Estado**: Accepted (registro verificable en GitHub pendiente)
- **Autoridad**: aprobada por la dirección del proyecto en sesión de trabajo del 2026-11-25.
  El registro verificable es un comentario personal de la persona mantenedora en el
  [issue #2](https://github.com/vyolete/financial-data-hub/issues/2); aún no consta.

## Contexto

FDH-001 necesita descubrimiento, persistencia, API y portal ejecutables en local.

## Alternativas y evidencia

No hay comparativas ni pruebas técnicas documentadas. La elección es una decisión de dirección,
no un resultado de benchmark.

## Decisión

| Ámbito | Tecnología |
|---|---|
| Lenguaje y entorno del backend | Python con uv |
| API | FastAPI |
| Persistencia | PostgreSQL |
| Portal | React |
| Entorno local | Docker Compose |
| Pruebas del backend | pytest |

dlt y Dagster son candidatos para etapas posteriores, sujetos a pruebas técnicas. No se instalan
en FDH-001.

## Consecuencias

El plan de FDH-001 fija versiones, bibliotecas (acceso a datos, migraciones, cliente HTTP),
lenguaje y herramientas del frontend, y pruebas del portal. Las versiones quedan en los archivos
de bloqueo.
