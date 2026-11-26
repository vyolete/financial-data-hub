# Arquitectura objetivo

**Estado**: objetivo aprobado por la mantenedora el 2026-11-25 (decisiones en los ADR aprobados: [registro](https://github.com/vyolete/financial-data-hub/issues/2#issuecomment-7179859703)). **Nada está implementado todavía.** Decisiones: [ADR-0002](../adr/0002-modular-monolith.md), [ADR-0003](../adr/0003-technology-stack.md), [ADR-0006](../adr/0006-metadata-driven-architecture.md), [ADR-0007](../adr/0007-integration-and-orchestration.md).

Diagrama editable: [target-architecture.drawio](target-architecture.drawio) (abrir con draw.io o diagrams.net).

## Enfoque

Plataforma de ingeniería de datos financieros y económicos cuyo componente central es un motor modular de integración ETL/ELT. Permite descubrir, configurar, extraer, transformar, almacenar, automatizar, consultar y distribuir datos con calidad, trazabilidad, eficiencia y confiabilidad.

Es un monolito modular orientado a metadatos: el plano de control describe **qué** hacer y registra lo ocurrido; el plano de datos **lo ejecuta**. La separación es lógica.

La asignación de componentes a etapas es una **propuesta** que cada especificación confirma.

## Plano de control

| Componente | Responsabilidad | Etapa propuesta |
|---|---|---|
| Registro y catálogo de fuentes | Fuentes, datasets, metadatos, atribución y permisos de metadatos, extracción y redistribución, administrados por configuración o comando local | FDH-001 |
| Configuración de conectores | Parámetros, límites y referencias a secretos | FDH-001 (descubrimiento), FDH-002 |
| Configuración de pipelines | Qué se extrae, cómo se transforma y dónde se guarda | FDH-003 |
| Orquestación | Programación, dependencias y relanzamientos | FDH-005 |
| Estado y cursores | Posición de cada sincronización | FDH-003 |
| Historial de ejecuciones | Estado, conteos y errores de cada ejecución | FDH-001 |
| Gobierno y calidad de datos | Estados de revisión, reglas de calidad y linaje | FDH-001 (revisión), FDH-004 |
| Observabilidad | Logs y métricas; alertas y objetivos de servicio | Desde FDH-001, FDH-008 |

## Plano de datos

| Componente | Responsabilidad | Etapa propuesta |
|---|---|---|
| Framework de conectores | Contratos, capacidades declaradas y adaptadores hacia las fuentes | FDH-001 (descubrimiento), FDH-002 |
| Motor de extracción e integración | Extraer y cargar según la configuración | FDH-003 |
| Procesamiento por lotes | Ejecutar cargas y transformaciones acotadas | FDH-003 |
| Sincronización incremental | Traer solo cambios usando el estado registrado | FDH-003 |
| Bronze | Conservar los datos originales sin modificarlos | FDH-004 |
| Silver | Normalizar y validar | FDH-004 |
| Gold | Productos de datos y vistas analíticas | FDH-004, FDH-007 |
| Servicios de consulta y exportación | API y exportaciones para consumidores | FDH-001 (catálogo), FDH-006 |

## Familias de conectores

| Familia | Uso previsto | Primera prueba |
|---|---|---|
| Socrata | Portales Socrata | Descubrimiento en datos.gov.co (FDH-001) |
| REST | API HTTP generales (candidata: World Bank Indicators, FDH-002 y FDH-003) | — |
| SDMX | Intercambio estadístico (candidatos: IMF, OECD; por verificar) | — |
| Archivos | CSV, Excel y Parquet | — |
| Especializados | Fuentes que no encajan en las anteriores | Descubrimiento en Data360, que es una API REST con contrato propio (FDH-001) |

## Flujos

| Flujo | Secuencia | Etapa |
|---|---|---|
| Descubrimiento | Comando local → configuración de la fuente → el adaptador construye la solicitud → el núcleo la ejecuta → el adaptador traduce la respuesta → catálogo e historial → API → portal | FDH-001 |
| Integración | Pipeline configurado → orquestación → motor → conector → Bronze → Silver → Gold | FDH-003 a FDH-005 |
| Estado y observabilidad | El plano de datos informa estado, cursores, conteos y métricas al plano de control | Progresivo |
| Consumo | Servicios → portal (React), Python, R y Power BI | FDH-001 (catálogo), FDH-006 |

## Reglas de separación

1. El plano de datos recibe configuración y registra resultados solo mediante interfaces del plano de control.
2. El plano de control no transporta ni transforma datos de los datasets.
3. El portal y los consumidores acceden mediante la API documentada, nunca directamente a la base de datos.
4. Los adaptadores no acceden a la red ni a la base de datos, ni deciden permisos ([propuesta de contrato](../../research/experiments/discovery-probe/discovery-contract-proposal.md)).
5. Un proceso desplegable adicional requiere un ADR.

## Tecnologías

| Tecnología | Papel | Situación |
|---|---|---|
| Python, uv | Backend y entorno | Adoptada |
| FastAPI | API | Adoptada |
| PostgreSQL | Metadatos y estado | Adoptada |
| React, con apoyo de Lovable | Portal | Adoptada; integración de Lovable por verificar |
| Docker Compose | Entorno local | Adoptada |
| pytest, GitHub Actions | Pruebas e integración continua desde FDH-001, proporcional al alcance | Adoptadas; sin configurar |
| Parquet y almacenamiento de objetos | Capas de datos | Objetivo; producto por elegir |
| dlt | Motor de integración | Referencia condicionada a pruebas de concepto |
| Dagster | Orquestador | Referencia condicionada a pruebas de concepto |
| Airbyte, Meltano, motor Python | Alternativas de comparación | Por evaluar |
| DuckDB | Analítica | Por evaluar |
| Logs, métricas y herramientas especializadas | Observabilidad | Progresiva |

## Alcance de FDH-001

Registro y catálogo, historial de ejecuciones, adaptadores de descubrimiento para Socrata y Data360, API de catálogo y portal de solo lectura, en local, con integración continua. No extrae datos ni incluye orquestación, capas de datos, dlt o Dagster. Ver la [especificación](../../specs/001-source-discovery/spec.md).
