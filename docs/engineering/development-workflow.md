# Flujo de desarrollo

1. Identificar necesidad e issue.
2. Redactar especificación con requisitos identificables, alcance, escenarios y criterios verificables.
3. Investigar incertidumbres y registrar evidencia.
4. Revisar y aprobar alcance; elaborar plan, contratos y tareas; aprobar decisiones relevantes.
5. Implementar en rama aislada con pruebas.
6. Revisar consistencia entre requisitos, código, pruebas y evidencia.
7. Abrir PR, obtener aprobación humana e integrar solo con autorización.
8. Actualizar especificaciones y contratos afectados al evolucionar el sistema.

Estados de especificación: Draft, In Review, Approved, In Progress, Verified, Released. Una investigación puede ejecutarse antes de aprobar una implementación productiva.

Convenciones propuestas: rutas en inglés kebab-case, módulos Python snake_case, Markdown, fechas ISO 8601 y timestamps UTC. Idioma definitivo, framework SDD y stack pendientes. No simular carpetas de un framework no instalado. La constitución formal se aprobará en la fase SDD Foundation.

Definición de terminado: criterios satisfechos con evidencia, pruebas y limitaciones explícitas, documentación coherente y revisión humana. Los controles automáticos y protección de ramas aún no están configurados.
