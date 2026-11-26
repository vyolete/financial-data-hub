# Análisis de consistencia de FDH-001

Resultado de `speckit-analyze` del 2026-11-26 sobre [spec.md](spec.md), [plan.md](plan.md) y [tasks.md](tasks.md), contra la constitución 1.1.1. El análisis fue de solo lectura: **ningún hallazgo está corregido**. Este archivo registra el informe para su revisión.

**Veredicto**: no iniciar `speckit-implement` sin resolver C1, C2, H1 y H2.

## Hallazgos

| ID | Categoría | Severidad | Ubicación | Resumen | Recomendación |
|----|-----------|-----------|-----------|---------|---------------|
| C1 | Constitución I | CRITICAL | tasks.md T003, T068 | Dos tareas no citan ningún requisito; la constitución exige que cada tarea cite al menos uno | T003: NFR-03. T068: FR-05 |
| C2 | Constitución V | CRITICAL | data-model.md `sources`; contracts/sources-config.md | Cada fuente debe registrar su licencia; el modelo y la configuración solo tienen condiciones de acceso y redistribución. El plan declara «Cumple» | Añadir licencia y URL de condiciones por fuente (desconocido por defecto) en modelo, configuración, API y tareas T016, T018, T020, T060 |
| H1 | Inconsistencia | HIGH | spec.md AC-14; contracts/openapi.yaml `DatasetDetail` | El criterio exige que el detalle devuelva la procedencia; el contrato solo la ofrece en un recurso aparte | Incluir en el detalle las observaciones más recientes, con máximo fijo, y su total; conservar la colección paginada |
| H2 | Subespecificación | HIGH | tasks.md T005, T006; quickstart.md | `config/sources.toml` está fuera del contexto de la imagen y ninguna tarea lo monta: `fdh` en Compose no tendría configuración | Montarlo en solo lectura en `compose.yaml` y definir su ruta por variable de entorno |
| M1 | Orden de tareas | MEDIUM | tasks.md T033, T035, T044, T063 | `persistence/session.py` se crea en US1, pero lo usan otras líneas declaradas paralelas; T035 está marcada `[P]` junto a T033 | Mover `session.py` a Fundamentos |
| M2 | Seguridad | MEDIUM | contracts/cli.md; plan.md paso 1 | Revocar el permiso de publicación solo surte efecto al ejecutar `discover`, que necesita red | Añadir `fdh sources sync`, sin solicitudes externas, con su tarea y prueba |
| M3 | Subespecificación | MEDIUM | tasks.md T002, T008, punto de control E0 | Con el esqueleto vacío, pytest y Vitest terminan con error sin pruebas, y la cobertura mínima no puede evaluarse | Incluir una prueba mínima en cada proyecto y activar el umbral al existir código |
| M4 | Cobertura no funcional | MEDIUM | tasks.md T066 | La búsqueda de secretos llega en E4, cuando ya hay código publicado | Adelantar gitleaks a T008 |
| M5 | Subespecificación | MEDIUM | data-model.md `runs` | No se define cómo contar un dataset visto dos veces en la misma ejecución | Contar por dataset distinto en `created`, `updated` y `unchanged`; las repeticiones solo en `received`; probarlo |
| M6 | Riesgo no verificado | MEDIUM | tasks.md T002 | No está comprobado que el bloqueo de sockets conviva con asyncio y asyncpg contra PostgreSQL local | Verificarlo en T002 con una prueba y documentar las opciones usadas |
| L1 | Inconsistencia | LOW | tasks.md «Trabajo en paralelo» | `registry.py` y `cli/main.py` se declaran exclusivos del integrador, pero T032, T059 y T065 se asignan a espacios aislados | El espacio entrega su módulo; el integrador hace el registro |
| L2 | Terminología | LOW | data-model.md, openapi.yaml, adapter-contract.md | Las fechas de origen se llaman `*_at_source` en datos y `*_at` en contrato y API | Documentar la correspondencia o unificar |
| L3 | Estructura | LOW | plan.md; tasks.md | El plan sitúa fuentes, catálogo y ejecuciones en `controlplane`, pero las tareas solo crean `ports.py` y `review.py` | Aclarar que su lógica vive en persistencia tras esas interfaces |
| L4 | Documentación | LOW | spec.md «Puntos abiertos» | Los cuatro puntos están resueltos en el plan y siguen listados como abiertos | Actualizar con autorización, sin cambiar requisitos |
| L5 | Flujo | LOW | tasks.md | Ninguna tarea pasa la especificación a `In Progress` | Añadirla al inicio de la implementación |
| L6 | Verificabilidad | LOW | tasks.md T072 | Comprobar que un fallo de CI es visible requiere una ejecución fallida | Definir cómo provocarla sin dejar la rama rota |
| L7 | Trazabilidad | LOW | tasks.md | Varias tareas citan criterios sin citar el requisito al que pertenecen | Completar las referencias |

## Cobertura por requisito

| Requisito | ¿Tiene tareas? | Tareas | Notas |
|---|---|---|---|
| FDH-001-FR-01 | Sí | 10 | |
| FDH-001-FR-02 | Sí | 6 | |
| FDH-001-FR-03 | Sí | 13 | Ver M5 |
| FDH-001-FR-04 | Sí | 8 | Ver H1 |
| FDH-001-FR-05 | Sí | 8 | |
| FDH-001-FR-06 | Sí | 9 | |
| FDH-001-NFR-01 | Sí | 11 | Ver M4 |
| FDH-001-NFR-02 | Sí | 17 | Ver M2 |
| FDH-001-NFR-03 | Sí | 13 | Ver M3, M6 |

Los 37 criterios de aceptación tienen al menos una tarea, y todos una tarea de prueba o verificación (AC-20 se verifica con investigación documentada, T056).

## Alineación con la constitución
Incumplimientos: principios I (C1) y V (C2). La tabla de comprobación del plan debe corregirse para V.

## Tareas sin requisito
T003 y T068.

## Métricas

| Métrica | Valor |
|---|---|
| Requisitos | 9 |
| Criterios de aceptación | 37 |
| Tareas | 73 (US1 14, US2 17, US3 6, US4 4; resto transversales) |
| Cobertura de requisitos | 100 % |
| Criterios con tarea | 37 de 37 |
| Ambigüedades | 1 (M5) |
| Duplicaciones | 0 |
| Críticos | 2 |
| Altos / medios / bajos | 2 / 6 / 7 |

## Comprobaciones ejecutadas y límites
- Automáticas, de solo lectura: formato e identificadores de las 73 tareas, etiquetas de historia, rutas, cobertura de requisitos y criterios, dependencias hacia adelante, asignación a líneas paralelas y marcadores sin resolver.
- Revisión de contenido hecha por el mismo agente que redactó el plan y las tareas; no es una revisión independiente.
- No se validó el OpenAPI con un validador de esquema ni se ejecutó el código del contrato en Python 3.13: la ejecución de esas herramientas fue denegada por los permisos de la sesión. Solo se comprobó la resolución de referencias y la sintaxis.

## Siguientes acciones
1. Autorizar la corrección de C1, C2, H1 y H2, y de preferencia M1 a M6, en plan, contratos y tareas. Ninguna cambia requisitos aprobados.
2. Repetir `speckit-analyze`.
3. Iniciar `speckit-implement` solo sin hallazgos críticos.
