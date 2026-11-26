# Estructura del repositorio: actual y objetivo

Complementa la [arquitectura objetivo](target-architecture.md), que describe componentes y flujos; este documento dice **dónde vive cada responsabilidad en el código**. La estructura actual describe archivos que existen. La estructura objetivo es una **propuesta**: cada especificación confirma sus módulos y nombres, y ningún directorio se crea antes de tener contenido.

**Situación descrita**: entrega E0 de FDH-001 (commit `d35141260db86ccd71b91f4b1525ba8a6d9fede3`).

## Estructura actual

```text
backend/                     # un único backend desplegable (API y CLI, misma imagen)
├── migrations/              # migraciones Alembic
├── src/fdh/
│   ├── domain/              # tipos y reglas puras
│   ├── controlplane/        # fuentes: plan de sincronización e interfaces de repositorio
│   ├── dataplane/
│   │   ├── connectors/      # contrato y registro de adaptadores (sin adaptadores)
│   │   └── discovery/       # paquete reservado en E0, sin motor
│   ├── persistence/         # modelos, sesiones y repositorio de fuentes (PostgreSQL)
│   ├── api/                 # FastAPI: solo /health
│   ├── cli/                 # `fdh config check` y `fdh sources sync`
│   ├── settings/            # entorno y config/sources.toml
│   └── observability/       # logs JSON sanitizados
└── tests/                   # unit, contract, integration, api, architecture, live, fixtures
frontend/                    # portal React: página inicial con el estado del servicio
config/sources.toml          # fuentes de descubrimiento, sin secretos
compose.yaml                 # entorno local: db, migrate, api, web
scripts/                     # comprobación de Compose y prueba de humo
specs/                       # especificaciones, planes y contratos (Spec Kit)
docs/                        # arquitectura, ADR, gobierno e ingeniería
research/                    # evidencia y experimentos aislados del producto
```

## Planos y módulos

El monolito modular separa lógicamente dos planos ([ADR-0002](../adr/0002-modular-monolith.md), [ADR-0006](../adr/0006-metadata-driven-architecture.md)):

- **Plano de control** (`controlplane/`): qué hacer y qué ocurrió. Fuentes, permisos, catálogo, ejecuciones, revisión y, más adelante, pipelines, cursores y programación.
- **Plano de datos** (`dataplane/`): ejecutarlo. Conectores, descubrimiento y, más adelante, extracción, transformación, almacenamiento y consulta.

`backend/` y `frontend/` se mantienen separados: el portal solo usa la API HTTP documentada.

| Módulo | Responsabilidad | No hace | Puede importar |
|---|---|---|---|
| `domain` | Datasets, localizadores, permisos, estados, definición de fuente | Entrada o salida | Biblioteca estándar |
| `controlplane` | Reglas del plano de control e interfaces que exige a la persistencia | SQL, red | `domain` |
| `dataplane.connectors` | Traducir entre el contrato común y cada plataforma | Red, base de datos, reloj, permisos | `domain` y su contrato |
| `dataplane.discovery` | Orquestar una ejecución de descubrimiento y su política de red | SQL, conocer una plataforma concreta | `domain`, contrato de conectores, `controlplane`, `httpx` |
| `persistence` | Implementar las interfaces sobre PostgreSQL | Decidir permisos o políticas | `domain`, `controlplane`, SQLAlchemy |
| `settings` | Leer y validar entorno y configuración | Red, base de datos | `domain`, Pydantic |
| `observability` | Logs estructurados y ocultación de secretos | Reglas de negocio | Biblioteca estándar |
| `api` | Exponer el catálogo en modo de solo lectura | Importar conectores | Dominio, control, persistencia, configuración, logs |
| `cli` | Componer los módulos para las operaciones locales | Reglas de negocio | Todos |

Las reglas de importación se comprueban en [test_import_rules.py](../../backend/tests/architecture/test_import_rules.py). Un módulo nuevo añade allí su regla en el mismo cambio.

## Evolución objetivo

Etapas del [roadmap](../../ROADMAP.md). Las rutas marcadas como propuestas **no existen**; se decidirán en la especificación y el plan de cada etapa.

| Capacidad | Ubicación | Etapa | Evolución prevista |
|---|---|---|---|
| Descubrimiento | `dataplane/discovery/`, `dataplane/connectors/<platform>/` | FDH-001 | Motor común y un adaptador por plataforma: Socrata y Data360 |
| Conectores reutilizables | `dataplane/connectors/` | FDH-002 | Ampliar el contrato a la extracción y organizar por familias (REST, SDMX, archivos, especializados) |
| Extracción | `dataplane/extraction/` (propuesta) | FDH-003 | Lotes acotados e incremental; exige permiso de extracción `allowed` |
| Integración ETL/ELT | `dataplane/integration/` (propuesta) y `controlplane/pipelines` (propuesta) | FDH-003 | Pipelines configurados; dlt y alternativas solo tras pruebas de concepto y ADR ([ADR-0007](../adr/0007-integration-and-orchestration.md)) |
| Estado y cursores | `controlplane/`, tablas en `persistence/` | FDH-003 | Posición de cada sincronización |
| Almacenamiento Bronze, Silver, Gold | `dataplane/storage/` (propuesta) | FDH-004 | Originales inmutables, normalización, productos y linaje; Parquet y almacenamiento de objetos por elegir |
| Calidad y gobierno | `domain/`, `controlplane/` | FDH-001 (revisión), FDH-004 | Estados de revisión; después reglas de calidad y linaje |
| Orquestación | `controlplane/orchestration/` (propuesta) | FDH-005 | Programación, dependencias y relanzamientos; Dagster condicionado a ADR-0007. Un proceso desplegable adicional exige un ADR |
| Servicios de datos | `api/`, `cli/` | FDH-001 (catálogo), FDH-006 | Consulta y exportación para Python, R y Power BI |
| Analítica | `dataplane/analytics/` (propuesta), `frontend/` | FDH-007 | Productos sobre Gold; DuckDB por evaluar |
| Observabilidad y operación | `observability/`, historial en `controlplane/` | Desde FDH-001; FDH-008 | Logs e historial; después métricas, alertas, objetivos de servicio y recuperación |

## Reglas para crecer

1. El motor común (red, reintentos, límites, deduplicación, procedencia, estados) no se duplica por plataforma. Una plataforma nueva aporta un adaptador y su registro.
2. Un directorio se crea con su primer código, sus pruebas y su regla de importación.
3. No se reorganiza código existente sin una necesidad de una especificación.
4. `research/` no es dependencia del producto.
5. Mantener este documento en el mismo cambio que mueva, añada o elimine un módulo.
