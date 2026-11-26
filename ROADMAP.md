# Roadmap

Etapas aprobadas por la mantenedora el 2026-11-25, sin fechas comprometidas. Los resultados esperados son una descripción inicial que cada especificación concreta.

| Etapa | Resultado esperado | Estado |
|---|---|---|
| FDH-000 Project Foundation | Gobierno, contexto común, flujo de trabajo, Spec Kit y constitución | En revisión |
| FDH-001 Discovery & Catalog | Descubrimiento y catálogo verificables de Socrata y World Bank | En revisión ([especificación](specs/001-source-discovery/spec.md)) |
| FDH-002 Connector Framework | Contratos y conectores reutilizables | Pendiente |
| FDH-003 Integration Engine | Extracción por lotes e incremental; pruebas de concepto ETL/ELT | Pendiente |
| FDH-004 Data Storage | Bronze, Silver y Gold, calidad, revisiones y linaje | Pendiente |
| FDH-005 Orchestration | Programación, dependencias y recuperación | Pendiente |
| FDH-006 Data Services | API, exportación y consumo analítico | Pendiente |
| FDH-007 Financial Analytics | Productos y vistas analíticas | Pendiente |
| FDH-008 Reliability & Operations | Objetivos de servicio, recuperación y escalabilidad validados | Pendiente |

El portal evoluciona junto con los componentes funcionales. La seguridad, las pruebas, la observabilidad y la eficiencia se incorporan desde las primeras entregas. La investigación de fuentes acompaña a la etapa que las integra y se registra en el [inventario](research/sources/inventory.md). Las pruebas de concepto de [ADR-0007](docs/adr/0007-integration-and-orchestration.md) preceden a la selección definitiva de integración y orquestación.

Cada etapa requiere criterios de aceptación y revisión. Issues y PR registran el estado operativo; este documento no duplica tareas.
