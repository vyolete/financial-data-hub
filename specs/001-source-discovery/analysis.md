# Análisis de consistencia de FDH-001

Resultados de `speckit-analyze` sobre [spec.md](spec.md), [plan.md](plan.md) y [tasks.md](tasks.md), contra la constitución 1.1.1. Revisión hecha por el mismo agente que redactó los artefactos; no es independiente.

## Segundo análisis (2026-11-26)

**Veredicto**: 0 críticos, 0 altos y 0 medios abiertos. Puede iniciarse `speckit-implement` para E0 y los fundamentos.

### Hallazgos del primer análisis

| ID | Severidad | Estado | Corrección |
|----|-----------|--------|------------|
| C1 | Crítica | Corregido | T003 cita NFR-03 y T068 cita FR-05 |
| C2 | Crítica | Corregido | Licencia, URL de condiciones y fecha por fuente en modelo, configuración, API y tareas |
| H1 | Alta | Corregido | El detalle incluye las 20 observaciones más recientes y su total |
| H2 | Alta | Corregido | `config/` montada en solo lectura en los servicios del backend, con `FDH_CONFIG` |
| M1 | Media | Corregido | `session.py` pasa a T020, en Fundamentos |
| M2 | Media | Corregido | `fdh sources sync` revoca sin descubrimiento ni red (T023, T024) |
| M3 | Media | Corregido | Pruebas mínimas desde E0 (T003, T004) |
| M4 | Media | Corregido | gitleaks desde T008 |
| M5 | Media | Corregido | Regla de conteo de repetidos definida y probada (T029) |
| M6 | Media | Corregido en el plan | T002 verifica el bloqueo de red con asyncio y la base local |
| L1 | Baja | Corregido | Cada línea entrega su módulo; el integrador registra |
| L2 | Baja | Corregido | Tabla de correspondencia de fechas |
| L3 | Baja | Corregido | El plan aclara el reparto entre `controlplane` y `persistence` |
| L4 | Baja | **Aceptado** | La especificación aprobada conserva su lista de puntos abiertos; modificarla exigiría tocar un documento aprobado. Están resueltos en [research.md](research.md), D04 a D06 y D12 |
| L5 | Baja | Corregido | T001 pasa la especificación a `In Progress` |
| L6 | Baja | Corregido | Commit vacío con `[ci-fail-demo]` (T008, T072) |
| L7 | Baja | Corregido | Cada criterio citado va con un requisito propietario |

### Hallazgos nuevos del segundo análisis

| ID | Severidad | Hallazgo | Estado |
|----|-----------|----------|--------|
| N1 | Crítica | `openapi-spec-validator` y PyYAML sin justificar en el plan (principio III) | Corregido: plan y D16 |
| N2 | Media | El trabajo `compose` de CI se definía en T008 y T055 | Corregido: T008 lo crea y T055 solo amplía el humo |
| N3 | Baja | E0 se describía a la vez como Fase 1 y como Fases 1 y 2 | Corregido: Fases 1 y 2 |

### Métricas

| Métrica | Valor |
|---|---|
| Requisitos con tarea | 9 de 9 |
| Criterios con tarea | 37 de 37 |
| Tareas | 73, todas con requisito |
| Hallazgos abiertos | 1 bajo, aceptado (L4) |

### Comprobaciones
- Automáticas: identificadores y referencias de tareas, requisitos y criterios, dependencias, presencia de cada corrección y marcadores sin resolver.
- OpenAPI validado con `openapi-spec-validator` 0.9.0: `OK`.
- Compatibilidad de Python 3.13, PostgreSQL 18 y dependencias comprobada ([research.md](research.md), D15).

## Primer análisis (2026-11-26)
Detectó 2 hallazgos críticos, 2 altos, 6 medios y 7 bajos. El informe completo está en el commit `679235d`.
