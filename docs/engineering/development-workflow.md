# Flujo de desarrollo

Se aplica con GitHub Spec Kit ([ADR-0001](../adr/0001-adopt-github-spec-kit.md)) y las puertas de la [constitución](../../.specify/memory/constitution.md).

1. Identificar necesidad e issue.
2. Redactar especificación con requisitos identificables, alcance, escenarios y criterios verificables (`speckit-specify`; `speckit-clarify` para ambigüedades).
3. Investigar incertidumbres y registrar evidencia.
4. Revisar y aprobar alcance; elaborar plan, contratos y tareas (`speckit-plan`, `speckit-tasks`, `speckit-analyze`); aprobar decisiones relevantes.
5. Implementar en rama aislada con pruebas (`speckit-implement`).
6. Revisar consistencia entre requisitos, código, pruebas y evidencia.
7. Abrir PR, obtener aprobación humana e integrar solo con autorización.
8. Actualizar especificaciones y contratos afectados al evolucionar el sistema.

Estados de especificación: Draft, In Review, Approved, In Progress, Verified, Released. Una investigación puede ejecutarse antes de aprobar una implementación productiva.

## Registro de aprobación
La persona mantenedora publica personalmente en el issue o PR un comentario como `APPROVED: <artefacto> @ <SHA>`, o aprueba mediante revisión o fusión. El artefacto enlaza ese registro. GitHub no permite aprobar con una revisión un PR propio; en ese caso sirve el comentario. Un commit sin push no puede aprobarse porque no es verificable en GitHub.

## Convenciones
Rutas en inglés kebab-case, módulos Python snake_case, Markdown, fechas ISO 8601 y timestamps UTC. Idiomas según [ADR-0005](../adr/0005-language-and-shared-memory.md) y stack según [ADR-0003](../adr/0003-technology-stack.md). No simular carpetas de un framework no instalado.

Definición de terminado: criterios satisfechos con evidencia, pruebas y limitaciones explícitas, documentación coherente y revisión humana. No hay pruebas automáticas en CI ni protección de ramas configuradas; ver el estado verificado en [SECURITY.md](../../SECURITY.md).
