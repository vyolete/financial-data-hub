# Plan de implementación: FDH-001 — Descubrimiento y catálogo

**Rama**: `feature/fdh-001-discovery-catalog` | **Fecha**: 2026-11-26 | **Especificación**: [spec.md](spec.md) (Approved)

## Resumen

Primer MVP funcional: un comando local descubre datasets en Datos Abiertos Colombia (Socrata) y World Bank Data360, guarda metadatos, procedencia e historial en PostgreSQL, y los expone mediante una API de solo lectura y un portal React. Es un monolito modular con plano de control y plano de datos separados lógicamente. No extrae datos.

Detalle: [investigación y decisiones](research.md), [modelo de datos](data-model.md), contratos de [API](contracts/openapi.yaml), [adaptadores](contracts/adapter-contract.md), [CLI](contracts/cli.md) y [configuración](contracts/sources-config.md), y [guía de validación](quickstart.md).

## Contexto técnico

| Aspecto | Decisión |
|---|---|
| Lenguaje | Python 3.13 (backend), TypeScript 5.9 (portal) |
| Dependencias de ejecución | FastAPI, Pydantic, pydantic-settings, Uvicorn, SQLAlchemy asíncrono, asyncpg, Alembic, httpx; React, React Router, TanStack Query, openapi-fetch |
| Dependencias de desarrollo | pytest, pytest-asyncio, pytest-socket, pytest-cov, ruff, mypy, openapi-spec-validator, PyYAML; Vite, Vitest, Testing Library, jsdom, ESLint, openapi-typescript |
| Herramientas de CI | gitleaks, pip-audit, npm audit |
| Almacenamiento | PostgreSQL 18 |
| Plataforma | Contenedores Linux con Docker Compose, solo en el equipo local |
| Tipo de proyecto | Aplicación web: backend con API y CLI, más SPA |
| Objetivos de rendimiento | La especificación no fija ninguno; no se declaran |
| Restricciones | Límites de la especificación; sin autenticación, solo local; sin extracción de datos |
| Escala | Dos fuentes; hasta 500 resultados por consulta; miles de datasets |

Cada dependencia se justifica en [research.md](research.md) (D02, D03, D09, D11, D16). Las versiones exactas quedan en `backend/uv.lock` y `frontend/package-lock.json`. Antes de fijarlas se comprueba que su licencia sea compatible con Apache-2.0.

## Comprobación contra la constitución

Constitución 1.1.1. Evaluada antes de la Fase 0 y repetida tras el diseño.

| Principio | Cómo se cumple | Antes | Después |
|---|---|---|---|
| I. Specification First | Especificación `Approved` con registro; contratos y tareas citan requisitos | Cumple | Cumple |
| II. Evidence First | Ambas API probadas en vivo y condiciones consultadas; una tarea revisa la referencia oficial de Socrata antes de su adaptador | Cumple | Cumple |
| III. Modularidad | Un backend; planos separados; adaptadores sin red ni persistencia; portal solo contra la API | Cumple | Cumple |
| IV. Integridad | Unicidad `(source_id, external_id)`; procedencia por observación; migraciones; desconocidos explícitos. Bronze, Silver y Gold no aplican porque no se extraen datos | Cumple | Cumple |
| V. Seguridad | Secretos por entorno; hosts permitidos; contenido externo tratado como dato; URL, verificación, licencia, acceso y redistribución por fuente; permisos por defecto `undetermined` y revocables sin red | Cumple | Cumple |
| VI. Eficiencia | Límites numéricos fijados; API paginada, también las colecciones auxiliares | Cumple | Cumple |
| VII. Observabilidad | Registro persistente por ejecución, logs con identificador y estados visibles | Cumple | Cumple |
| VIII. Pruebas | pytest, PostgreSQL real, sin red, bloqueos versionados y CI desde la primera entrega | Cumple | Cumple |
| IX. Colaboración | Aprobación registrada; espacios aislados sin ramas nuevas; un integrador | Cumple | Cumple |

Sin violaciones que justificar.

## Estructura del proyecto

### Documentación

```text
specs/001-source-discovery/
├── spec.md          # aprobada; no se modifica
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi.yaml
│   ├── adapter-contract.md
│   ├── cli.md
│   └── sources-config.md
└── tasks.md
```

### Código

```text
backend/
├── pyproject.toml, uv.lock, Dockerfile, alembic.ini
├── migrations/
├── src/fdh/
│   ├── domain/            # tipos puros: estados, permisos, localizadores
│   ├── controlplane/      # fuentes, catálogo, ejecuciones, revisión
│   ├── dataplane/
│   │   ├── connectors/    # contract.py, registry.py, socrata/, data360/
│   │   └── discovery/     # motor, ejecutor HTTP, reintentos
│   ├── persistence/       # modelos y repositorios SQLAlchemy
│   ├── api/               # FastAPI
│   ├── cli/               # comando `fdh`
│   ├── settings/          # entorno y sources.toml
│   └── observability/     # logging
└── tests/
    ├── unit/  contract/  integration/  api/  architecture/  live/
    └── fixtures/synthetic/
frontend/
├── package.json, package-lock.json, Dockerfile, nginx.conf
└── src/
    ├── api/               # tipos generados, cliente y consultas
    ├── components/        # presentación, sin red ni enrutador
    ├── pages/
    └── test/
config/sources.toml
compose.yaml
.env.example
.github/workflows/ci.yml
```

**Decisión de estructura**: `backend/` y `frontend/` separados; API y CLI comparten paquete e imagen. `controlplane` define las interfaces y las reglas de fuentes, catálogo, ejecuciones y revisión; `persistence` las implementa.

### Reglas de dependencia

| Módulo | Puede importar |
|---|---|
| `domain` | Biblioteca estándar |
| `settings` | `domain` y Pydantic |
| `observability` | Biblioteca estándar |
| `dataplane.connectors` | `domain` y su contrato. Nunca `httpx`, `sqlalchemy`, `asyncpg`, sockets ni persistencia |
| `controlplane` | `domain`; define las interfaces de repositorio |
| `dataplane.discovery` | `domain`, el contrato de conectores y las interfaces de `controlplane` |
| `persistence` | `domain` e interfaces de `controlplane` |
| `api`, `cli` | Componen los anteriores; la API no importa conectores |

Una prueba de arquitectura analiza los imports y falla ante una violación.

## Diseño

### Contrato común de adaptadores
El adaptador es puro: `validate`, `build_request`, `classify` y `parse`, y declara sus capacidades. El núcleo ejecuta las solicitudes. Ver [adapter-contract.md](contracts/adapter-contract.md).

### Adaptadores

| Aspecto | Socrata | Data360 |
|---|---|---|
| Solicitud | `GET /api/catalog/v1` con `domains`, `only=datasets`, `q`, `limit`, `scroll_id` | `POST /data360/searchv2` con `search`, `filter="type eq 'dataset'"`, `top`, `skip`, `count=true` |
| Fin de páginas | Vistos ≥ `resultSetSize` o página vacía | `skip` + devueltos ≥ `@odata.count` o página vacía |
| Rechazo | Sin `resource.id` o sin nombre; tipo distinto de dataset | Sin `idno` o sin nombre; tipo distinto de dataset |
| Descarta | `owner`, `creator`, `contact_email` | Campos fuera del modelo |

La correspondencia de campos está en [adapter-contract.md](contracts/adapter-contract.md).

### Motor de descubrimiento
1. Cargar y validar `sources.toml`; sincronizar las fuentes con la misma operación que `fdh sources sync`, que funciona sin red. Una configuración inválida o una capacidad no soportada termina sin solicitudes (AC-33).
2. Tomar un bloqueo consultivo de PostgreSQL por fuente. Si ya está tomado, el comando termina sin crear ejecución. Al obtenerlo, cerrar las ejecuciones `running` abandonadas con un error `interrupted`.
3. Crear la ejecución `running` y confirmarla.
4. Por cada consulta, hasta `max_pages`: construir la solicitud, comprobar el host, ejecutar con reintentos, clasificar y traducir.
5. Guardar cada página en una transacción: datasets, localizadores, observaciones y conteos. Un fallo posterior conserva lo confirmado.
6. Un error de una consulta se registra y se continúa con la siguiente. Un `Retry-After` mayor de 60 s detiene la ejecución completa, para no insistir contra un proveedor que pide espera.
7. Por consulta, `truncated` es verdadero si queda cursor tras `max_pages`.
8. Estado final: `final_status(valid, rejected, failures)`, donde `valid` cuenta datasets válidos distintos de la ejecución.

### Política de red

| Regla | Valor |
|---|---|
| Plazo por intento, incluida la lectura | 10 s, configurable |
| Reintentos adicionales | 3; esperas de 1, 2 y 4 s, nunca menores que `Retry-After` |
| `Retry-After` | Segundos o fecha HTTP; mayor de 60 s: sin reintento |
| Reintentable | Fallo de conexión, plazo agotado, 429, 500, 502, 503, 504 |
| Hosts | Solo `allowed_hosts`, por HTTPS; sin seguir redirecciones |
| Tamaño máximo de respuesta | 10 MB; superarlo es un error permanente |

El reloj y la espera se inyectan para probar sin demoras.

### Persistencia y migraciones
Alembic con una migración inicial y `unaccent`. Detalle en [data-model.md](data-model.md). El servicio `migrate` aplica las migraciones antes de iniciar la API. La CI comprueba que los modelos y las migraciones coinciden.

### API
Solo lectura, versionada en `/api/v1`, según [openapi.yaml](contracts/openapi.yaml). El detalle incluye las 20 observaciones más recientes y su total; el historial completo está paginado. Solo devuelve datasets de fuentes `allowed` que no sean `restricted`; los demás responden 404. Sus conexiones se abren en modo de transacción de solo lectura. El contrato es la referencia: la CI compara el esquema generado con él.

### Portal

| Pantalla | Contenido | Estados |
|---|---|---|
| Catálogo | Búsqueda, filtros por proveedor y categoría, paginación, atribución y licencias | Cargando, vacío, fallido |
| Detalle | Metadatos, licencias, permisos, revisión, localizadores y procedencia | Cargando, no encontrado, fallido |
| Ejecuciones | Estado, conteos, truncamiento y errores | Cargando, vacío, fallido |

El contenido externo se muestra como texto. Solo se enlazan URL HTTPS, con `rel="noopener noreferrer"`. Un dato ausente se muestra como «desconocido». La preparación para Lovable se describe en D09.

### Observabilidad y seguridad iniciales

| Control | Implementación |
|---|---|
| Logs | JSON, con `run_id`, fuente y evento; sin cuerpos, cabeceras ni credenciales; filtro que oculta valores sensibles |
| Historial | Ejecuciones, consultas y errores sanitizados en la base de datos |
| Salud | `GET /health` comprueba la API y la base de datos |
| Exposición | Puertos solo en `127.0.0.1`; validación de la cabecera `Host`; sin CORS (mismo origen) |
| Base de datos | Contraseña por `.env`; sin puerto público |
| Configuración | `config/` montada en solo lectura únicamente en los servicios del backend; nunca en la imagen ni en el portal |
| Contenedores | Usuario sin privilegios; imágenes fijadas por resumen |
| Navegador | Cabeceras CSP, `X-Content-Type-Options` y `Referrer-Policy` en nginx |
| Entradas | Validación de parámetros; consultas parametrizadas; comodines de búsqueda escapados |
| Cadena de suministro | Bloqueos versionados, acciones fijadas por SHA, búsqueda de secretos y auditoría informativa |

### Integración continua
Un flujo con `permissions: contents: read`, disparado por `push` en cualquier rama y por `pull_request`:

| Trabajo | Comprueba |
|---|---|
| `backend` | `uv sync --locked`, ruff, formato, mypy, pruebas unitarias, de contrato y arquitectura sin red |
| `integration` | Migraciones, `alembic check`, pruebas de integración y API contra PostgreSQL, deriva de OpenAPI |
| `frontend` | `npm ci`, ESLint, tipos, pruebas, tipos generados al día, compilación |
| `compose` | Configuración, puertos solo locales, construcción, arranque y humo con datos sintéticos |
| `security` | gitleaks (bloquea, desde E0) y auditoría de dependencias (informa) |

Ningún trabajo llama a las API externas.

## Pruebas y criterios de aceptación

| Capa | Criterios |
|---|---|
| Unitarias (dominio, reintentos, motor con ejecutor falso) | AC-08 a AC-11, AC-22, AC-23, AC-30, AC-32 |
| Contrato (adaptadores, sin red ni base de datos) | AC-01, AC-02, AC-07, AC-21, AC-33, AC-34, AC-36 |
| Integración (PostgreSQL) | AC-03 a AC-07, AC-09, AC-26, AC-35 |
| API | AC-12 a AC-15, AC-27, AC-31 |
| Portal | AC-16 a AC-18, AC-30, AC-31 |
| Arquitectura y seguridad | AC-24, AC-25, AC-34 |
| Humo y CI | AC-28, AC-37 |
| En vivo, manual y documentada | AC-19, AC-20, AC-29 |

## Entregas funcionales

| Entrega | Resultado demostrable | Requisitos principales |
|---|---|---|
| E0 Base | Proyecto, Compose, base de datos y CI en verde | NFR-01, NFR-03 |
| E1 Descubrimiento Socrata | `fdh discover` guarda datasets y ejecuciones reales | FR-01, FR-02, FR-03 |
| E2 Catálogo visible | API y portal muestran esos datasets y ejecuciones | FR-04, FR-05, NFR-02 |
| E3 Data360 | Segunda fuente sin cambiar el núcleo | FR-06 |
| E4 Cierre | Revisión de permisos, controles, clon limpio y evidencia en vivo | NFR-01 a NFR-03 |

E1 y E2 forman el primer corte utilizable.

## Trabajo en paralelo

```bash
git worktree add --detach ../fdh-ws-<nombre> HEAD   # crear, sin rama
git -C ../fdh-ws-<nombre> commit ...                 # trabajar aislado
git cherry-pick <sha>                                # integrar desde la copia principal
git worktree remove ../fdh-ws-<nombre>
```

Reglas: una sola sesión integra y publica; cada espacio toca archivos distintos; los contratos y tipos compartidos se integran antes de abrir los espacios; la numeración de migraciones la asigna el integrador. Cada espacio crea su `.specify/feature.json` si usa Spec Kit. Las tareas indican qué líneas pueden ejecutarse a la vez.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Cambios en la paginación de Socrata (`scroll_id`, confirmado en su referencia) | Paginación aislada en el adaptador y pruebas de contrato |
| Data360 en beta | Validación de cada respuesta y pruebas de contrato |
| Data360 sin URL oficial ni publicador | Se muestran como desconocidos; revisar si existe un patrón documentado |
| Licencias externas o ausentes | Permisos `undetermined`; revisión humana antes de extraer |
| Lovable usa otro stack en proyectos nuevos | Componentes sin dependencia de red ni enrutador; incorporación revisada |
| httpx sin versiones recientes | Uso aislado en el ejecutor |
| Respuestas de Socrata cercanas a 10 s | Plazo y tamaño de página configurables; medir en la evidencia en vivo |
| Directorio de datos distinto en la imagen de PostgreSQL 18 | Volumen en `/var/lib/postgresql` (comprobado, D15) y prueba de reinicio |

## Decisiones que requieren registro

Las decisiones D02 a D14 se aplican dentro del stack aprobado. La relación con Lovable (D09) precisa [ADR-0002](../../docs/adr/0002-modular-monolith.md): se propondrá como ADR-0009 en estado `Proposed`.

## Seguimiento de complejidad

No hay excepciones a la constitución.
