# Validación de FDH-001

## E0 y fundamentos (T001 a T024)

Ejecutada el 2026-11-26 (UTC) sobre el commit `40b6fb9c31a1e763b5faf1b4969a653543fc825d`, en macOS arm64 con Docker 28.1.1, Compose 2.35.1 y uv 0.13.10.

### Integración continua
[Ejecución 45741033954](https://github.com/vyolete/financial-data-hub/actions/runs/45741033954), evento `push`: los cinco trabajos terminaron correctamente.

| Trabajo | Resultado observado en los registros |
|---|---|
| `backend` | 198 pruebas sin red ni base de datos; cobertura 98,72 % de `domain` y `dataplane` |
| `integration` | Migración sin diferencias; 18 pruebas contra PostgreSQL 18 |
| `frontend` | ESLint, tipos, 5 pruebas y compilación |
| `compose` | Puertos locales y montaje de solo lectura; arranque, humo, CLI y persistencia tras reiniciar |
| `security` | gitleaks 8.30.1 sin hallazgos en el historial |

### Clon limpio local
Clon de la rama publicada, `.env` nuevo y proyecto de Compose independiente:

| Comando | Resultado |
|---|---|
| `docker compose up --detach --build --wait` | Código 0; reutilizó la caché de imágenes del equipo |
| `./scripts/smoke.sh` | `smoke test passed` |
| `docker compose run --rm api fdh config check` | Válida; adaptador `socrata` no disponible todavía |
| `docker compose run --rm api fdh sources sync` | 1 fuente; `undetermined -> allowed` |
| `uv sync --locked` y `uv run pytest` | 216 pruebas superadas |

### Comprobaciones locales adicionales
Hechas durante la implementación, antes de ese commit; después solo cambiaron el formato de los registros y los documentos.

- Contenedores: usuario sin privilegios (10001 y 101), sistema de archivos y configuración de solo lectura; sin pytest, dlt ni Dagster en la imagen.
- Revocación: una copia de la configuración con `denied` y evidencia sintética cambió el permiso con `fdh sources sync`, sin ejecuciones de descubrimiento. La base local se recreó después.
- Persistencia: los datos y la revisión `0001` se conservaron tras `docker compose down` y `up`.
- Base detenida: `/health` respondió 503 con un mensaje sin detalles internos; la contraseña no apareció en los registros.
- Portal en Chrome sin interfaz, con perfil temporal: «Servicio disponible», «Servicio no disponible» al detener la API y sin avisos de CSP.
- `npm audit`: 0 vulnerabilidades. gitleaks sin hallazgos en el historial y en los archivos a confirmar.

### No ejecutado o con salvedades
- No hay descubrimiento, adaptadores, API de catálogo ni catálogo en el portal.
- Ninguna prueba contactó las API externas.
- No se provocó el fallo intencional de CI (`[ci-fail-demo]`, T072).
- `pip-audit` no se ha ejecutado (T066).
- Las pruebas de dominio, configuración, planificación y logging se escribieron y fallaron antes de implementar; las de persistencia, CLI, API y portal se escribieron junto con su implementación o después.
- La construcción local no partió de una caché vacía.

### Incidencias de la implementación
- `pytest-socket` avisa antes de lanzar la excepción; se filtra ese aviso para que la prueba reciba el error.
- Uvicorn y Alembic escribían registros en texto; ahora usan el formato JSON.
- El equipo no tenía espacio: se borraron, con autorización, cachés de Cypress, Playwright, actualizadores, npm y JetBrains.

## E1: descubrimiento en Socrata (T025 a T038)

Ejecutada el 2026-11-26 (UTC) con la imagen del backend construida desde el commit `e53ebb5c76aaf4fc099160ecf5c00f20b7898a47`, en macOS arm64 con Docker 28.1.1, PostgreSQL 18 y `config/sources.toml` sin cambios. Las cifras dependen del catálogo remoto en ese momento.

### Descubrimiento real

Estado inicial: 1 fuente, 0 datasets y 0 ejecuciones. Comando, ejecutado dos veces: `docker compose run --rm api fdh discover --source co-datos-gov`. Ambas con código 0 y estado `succeeded`.

| Métrica | Primera (`fc75e30e`, 02:42:07Z) | Repetición (`f3698f26`, 02:42:32Z) |
|---|---|---|
| Solicitudes enviadas (con reintentos) | 4 | 4 |
| Páginas | 4 | 4 |
| Registros recibidos | 252 | 252 |
| Registros únicos | 237 | 237 |
| Creados / actualizados / sin cambios | 237 / 0 / 0 | 0 / 0 / 237 |
| Rechazados / fallos | 0 / 0 | 0 / 0 |
| Duración / persistencia, según la CLI | 1,64 s / 0,19 s | 1,50 s / 0,19 s |
| Duración registrada en la base (`finished_at - started_at`) | 1,62 s | 1,47 s |

| Consulta | Páginas | Total declarado | Truncada |
|---|---|---|---|
| `presupuesto` | 2 | 145 | no |
| `finanzas` | 2 | 107 | no |

### Persistencia consultada con SQL de solo lectura

| Comprobación | Tras la primera | Tras la repetición |
|---|---|---|
| Datasets / identidades `(source_id, external_id)` distintas | 237 / 237 | 237 / 237 |
| Localizadores | 474 | 474 |
| Observaciones de procedencia | 252 | 504 |
| Ejecuciones | 1 | 2 |
| Tamaño de la base (antes de descubrir, 8238 kB) | 8990 kB | 9470 kB |

- La huella de `id`, `external_id`, primera observación y primera ejecución de los 237 datasets fue idéntica antes y después de repetir; los 237 actualizaron su última observación.
- 15 datasets aparecieron en ambas consultas y conservan las dos en su historial (237 + 15 = 252).
- Los 237 quedan `pending`, con extracción y redistribución `undetermined` y sin condiciones atribuidas.
- Licencias declaradas, textuales: CC BY-SA 4.0 en 232, CC BY-ND 4.0 en 2, CC BY 4.0 en 2 y CC0 en 1; ninguno sin licencia.
- Localizadores: 237 `link` y 237 `permalink`, todos `unverified`; ninguno se consultó.
- Valores presentes sobre 237: descripción 236, publicador 237, URL oficial 237, categorías 228, etiquetas 192. `updated_at_source` queda desconocido en todos.
- El esquema no tiene columnas de propietarios, creadores ni contactos.

### Comportamiento ante errores

En una base de datos aislada, creada y eliminada para esta validación, con copias de la configuración fuera del repositorio. El catálogo anterior no cambió.

| Escenario | Fuente real | Salida | Observado |
|---|---|---|---|
| Opción desconocida | sin solicitudes | 2 | 0 ejecuciones y 0 datasets |
| Host de `base_url` no permitido | sin solicitudes | 2 | 0 ejecuciones y 0 datasets |
| Dominio inexistente | sí | 4 | HTTP 404, 1 solicitud, `failed`, 1,68 s |
| Plazo de 0,05 s por intento | sí | 4 | 4 solicitudes, esperas de 1, 2 y 4 s, `timeout`, `failed`, 7,30 s |
| Máximo de 1 página | sí | 0 | `succeeded`, 100 registros, `truncated`, total 145 |
| Dominio inexistente con datos previos | sí | 4 | Los 100 datasets quedaron idénticos |
| Fuente ocupada por otra sesión (bloqueo consultivo) | sin solicitudes | 5 | Sin ejecución nueva |
| Base de datos inalcanzable (puerto 1) | sin solicitudes | 1 | La contraseña no apareció en las salidas capturadas |
| Proceso terminado con `docker kill` y nueva ejecución | sí | 0 | La ejecución abandonada pasó de `running` a `failed` con `interrupted`; la nueva dejó 100 sin cambios |

### Pruebas automatizadas
Sobre el mismo código, sin red externa:

| Comando (en `backend/`) | Resultado |
|---|---|
| `uv run pytest` | 433 superadas, contra PostgreSQL 18 |
| `uv run pytest tests/unit tests/contract tests/architecture tests/api --cov=fdh.domain --cov=fdh.dataplane --cov-fail-under=85` | 375 superadas; cobertura 98,45 % |
| `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` | Sin hallazgos |
| `uv run alembic check` | Sin diferencias; E1 no añade migraciones |
| `uv run pytest -m live` | 1 superada contra Socrata ([evidencia](../../sources/colombia/socrata/evidence/live-2026-11-26T024122Z.json)) |

### No ejecutado o con salvedades
- Ningún registro real se rechazó: los rechazos, la ejecución `partial`, el 429, `Retry-After`, las redirecciones, el límite de 10 MB y un fallo de persistencia se probaron solo con datos sintéticos.
- No se provocaron límites del proveedor. No se usa app token, aunque la referencia oficial lo recomienda.
- La prueba de que un redescubrimiento no revierte decisiones humanas usa datos sintéticos; el comando de revisión es de E4 y no existe.
- Las pruebas del ejecutor HTTP, motor, adaptador, huella y persistencia fallaron antes de implementar por módulos inexistentes. Las de la CLI se escribieron antes, pero su fallo individual no se observó. La prueba en vivo se escribió después.
- Los adaptadores se probaron sin base de datos; no hay API ni portal de catálogo (E2), Data360 (E3) ni administración de permisos (E4).
- No se repitió el clon limpio local por espacio en disco; la integración continua parte de un clon limpio.
- En una ejecución interrumpida, `finished_at` es el momento en que se cerró, no el de la interrupción.
- Un cambio del orden de categorías, etiquetas o localizadores en la fuente contaría como actualización; no se observó entre las dos ejecuciones.

## E2 — verificación previa (2026-11-26 UTC)

Rama local `feature/fdh-001-discovery-catalog`, HEAD
`dc4cfa0f478112d0d41bda86468b33af6c2feb0b`. El [comentario de la mantenedora en el issue #2](https://github.com/vyolete/financial-data-hub/issues/2#issuecomment-7181780344)
cita `aa1d4f982f2bdb8e00be4175a603305451472c19` para AC-38 a AC-40 y T074 a T077.
`git show aa1d4f9` confirma ese contenido. `git diff aa1d4f9 HEAD -- specs/` solo muestra las
marcas de ejecución de T074 a T076. La API de GitHub devolvió HTTP 422 para el SHA citado y
`git ls-remote origin refs/heads/feature/fdh-001-discovery-catalog` devolvió `147621c`.
El flujo de desarrollo exige que el SHA aprobado sea verificable en GitHub.

| Comprobación | Resultado |
|---|---|
| `cd backend && .venv/bin/pytest -q tests/unit tests/contract tests/architecture` | 396 superadas (salida 0), con permiso para el socket local |
| `cd backend && .venv/bin/pytest -q tests/integration tests/architecture` | 158 superadas (salida 0) con PostgreSQL 18 y bases temporales. Se solapan las pruebas de arquitectura con la ejecución anterior |
| `cd backend && .venv/bin/pytest -q tests/unit/test_app_token.py tests/unit/test_http_executor.py` | 68 superadas (salida 0), subconjunto de la primera ejecución |
| `cd backend && .venv/bin/pytest -q tests/integration/test_migrations.py tests/integration/test_discover_cli.py -k 'migration or metrics or token'` | 18 superadas, 20 deseleccionadas (salida 0), subconjunto de integración |
| Pruebas de salud de `HEAD`, extraídas a un directorio temporal con `git show HEAD:backend/tests/api/test_health.py` | 7 superadas (salida 0). La versión local en preparación exige el argumento `queries`, pendiente de implementación |
| `npm ci --no-audit --no-fund && npm test`, en `node:24-alpine`, con el código y los archivos de configuración de `frontend/` copiados al contenedor | 5 superadas (salida 0). El intento local con Node 23 encontró incompatibilidades de versión y errores DNS |

**Migración y AC-40.** En PostgreSQL se clonó el catálogo local con `pg_dump -Fc` y
`pg_restore --exit-on-error` a una base desechable. Con `FDH_DB_NAME` apuntando a la copia,
`alembic upgrade head` aplicó `0001 → 0002` y `alembic check` devolvió
`No new upgrade operations detected`. Se compararon conteos y huellas de filas ordenadas
por ID, excluyendo las cuatro columnas nuevas al comparar las ejecuciones. Coincidieron 237
datasets, 504 observaciones y 2 ejecuciones. Las cuatro métricas quedaron en SQL `NULL` en
ambas ejecuciones históricas. La base original quedó en `0001`.

**App Token y AC-38/39.** Se revisó el flujo desde el entorno hasta el encabezado de la
plataforma. El ejecutor valida el host antes del envío y desactiva redirecciones. Las pruebas
usaron un token ficticio y cubrieron ausencia, valor mal formado, cabecera, ausencia en
salidas y persistencia, y espaciado con reloj falso. `.env` está ignorado por Git.

**Handoff.** Espacio disponible según `df -h .`: 2,7 GiB al inicio y 1,1 GiB en la
comprobación posterior. Las pruebas locales de Claude Code de T039–T041 y la semilla
sintética permanecen en `backend/tests/api/` y `backend/tests/fixtures/`, respectivamente.
Quedan pendientes T039–T055 y T077, incluida la comparación del OpenAPI generado y la
prueba en Chrome. No se ejecutó descubrimiento en vivo. La siguiente acción es resolver
la disponibilidad del SHA de aprobación en GitHub y reanudar en la misma rama local.

## E2 — implementación y validación local

Validación del 2026-11-26 UTC en `feature/fdh-001-discovery-catalog`, sobre
`dc4cfa0f478112d0d41bda86468b33af6c2feb0b` más los cambios locales. El bloqueo de la
verificación previa se resolvió al publicarse los dos commits base. GitHub devolvió
[el commit aprobado](https://github.com/vyolete/financial-data-hub/commit/aa1d4f982f2bdb8e00be4175a603305451472c19)
y el [comentario de vyolete](https://github.com/vyolete/financial-data-hub/issues/2#issuecomment-7181780344)
que cita el mismo SHA y autoriza E2. Las pruebas y fixtures locales de Claude Code se
conservaron. T039–T055 y T077 se verificaron localmente. La ejecución alojada de GitHub
Actions queda pendiente de una publicación autorizada.

| Tareas | Comprobación | Resultado |
|---|---|---|
| T039, T045, T046, T049 | `pytest tests/api/test_openapi_contract.py` en la suite, y `FDH_API_PYTHON=../backend/.venv/bin/python npm run api:check` en `frontend/` | Coinciden operaciones GET, IDs, parámetros, límites y esquemas de respuesta. Declaraciones TypeScript sin deriva |
| T040, T044, T047 | `pytest tests/api/test_datasets.py` con PostgreSQL 18 y una base desechable por prueba | Paginación, búsqueda sin tildes, comodines literales, filtros, visibilidad, licencias, procedencia y solo lectura |
| T041, T048, T076 | `pytest tests/api/test_runs.py` con PostgreSQL 18, incluido `-k redacts` | Estados, truncamiento, métricas y errores sanitizados. El caso de regresión conserva los campos estructurados y oculta el token ficticio |
| T042–T043 y T050–T054 | En `frontend/` con Node 24, `npm run lint && npm run typecheck && npm test && npm run build` | 11 pruebas en 4 archivos, lint, tipos y compilación correctos |
| T055, T077 | `FDH_EXPECT_SYNTHETIC=1 ./scripts/smoke.sh` y `node scripts/browser_check.mjs`, con URL y puertos locales alternativos | Humo y Chrome pasaron contra Nginx, FastAPI del árbol local y PostgreSQL 18 con la semilla sintética. Chrome comparó orden y contenido con la API, filtró, abrió detalle e historial, revisó visibilidad, estados y métricas, y distinguió carga, vacío, recurso ausente y fallo |
| T055 | `docker compose config --format json \| python3 scripts/check_compose.py` | Puertos en loopback y configuración de solo lectura |
| Backend | `ruff check .`, `ruff format --check .`, `mypy` y selección de CI con `--cov=fdh.domain --cov=fdh.dataplane --cov-fail-under=85` | Chequeos correctos. 437 pruebas en la selección de CI, cobertura de 98,48 % |
| Suite backend completa | `cd backend && .venv/bin/pytest -q --tb=short`, con las variables de PostgreSQL exportadas | 578 superadas (salida 0), una prueba en vivo deseleccionada |

### Migración e historial

Se repitió `pg_dump -Fc` y `pg_restore --exit-on-error` del catálogo original hacia una
base desechable de PostgreSQL 18. Con `FDH_DB_NAME` apuntando a la copia,
`alembic upgrade head` aplicó 0002 y `alembic check` informó
`No new upgrade operations detected`. Antes y después se compararon conteos y MD5 de
las filas serializadas y ordenadas por ID de `datasets`, `dataset_observations` y
`runs`. Para `runs` se excluyeron las cuatro columnas nuevas del cálculo. Coincidieron
237 datasets, 504 observaciones y 2 ejecuciones. Con FastAPI conectado a la copia se
verificó HTTP 200 en listado y detalle de datasets, total 237 y dos ejecuciones cuyo
detalle devuelve `null` en las cuatro métricas históricas. Una lectura final del
catálogo original confirmó revisión 0001 y los mismos conteos.

### Reproducción y handoff

Los comandos para un entorno desechable están en la
[guía de validación](../../../specs/001-source-discovery/quickstart.md#contrato-catálogo-sintético-y-chrome-e2).
Para la comprobación local con espacio limitado se reutilizaron las imágenes de
Node 24, FastAPI y Nginx disponibles. FastAPI cargó `backend/src/` por un montaje de
solo lectura. Nginx sirvió el bundle de producción con la configuración del repositorio,
cambiando únicamente el nombre del upstream para apuntar al FastAPI de prueba.
El browser check usó `FDH_BROWSER_URL=http://127.0.0.1:18080`. El bundle y su etapa
temporal de compilación quedaron en `/tmp/fdh-web-e2-stage`.

La implementación y su validación local quedan reunidas en el commit de cierre de E2.
La entrada del commit en GitHub, la revisión humana, la ejecución alojada de CI y el
descubrimiento en vivo de Socrata sobre esta revisión quedan pendientes. Visual Pipeline Studio permanece en su proyecto independiente y
puede integrar el catálogo mediante el [contrato HTTP de E2](../../../specs/001-source-discovery/contracts/openapi.yaml).

### Handoff de publicación

- **Rama** `feature/fdh-001-discovery-catalog`. Base publicada
  `dc4cfa0f478112d0d41bda86468b33af6c2feb0b`. Identificar el commit de cierre mediante
  `git log -1 --format=%H` al recibir esta revisión. El SHA del commit que contiene
  esta evidencia se comunica en el handoff de la sesión.
- **Alcance** T039–T055 y T077. Implementación y verificación local completadas.
  El contrato OpenAPI aprobado y la migración 0002 se conservan.
- **Comprobaciones de cierre** Se repitieron las 27 pruebas de salud, errores y contrato,
  Ruff, mypy, `api:check`, comprobaciones de sintaxis de los scripts y revisión del
  candidato a commit. Los resultados de PostgreSQL y Chrome de la sección anterior
  corresponden a la validación local de E2.
- **Siguiente acción** Con autorización explícita, publicar el commit en la misma rama,
  verificar los trabajos de GitHub Actions sobre su SHA y preparar la revisión funcional.
  La revisión cubre búsqueda y filtros, permisos de visibilidad, procedencia, estados
  del portal, métricas históricas y conservación del catálogo migrado en una copia.

### Diagnóstico y ajuste del arranque de Chrome en CI

Base publicada: `60d84f4906f7f3f557e3d6459b0eda1b344281fd`. En el
[primer intento](https://github.com/vyolete/financial-data-hub/actions/runs/45752180724/job/139682323638)
y el [segundo intento](https://github.com/vyolete/financial-data-hub/actions/runs/45752180724/job/139683131394),
Compose completó el arranque, la migración, el reinicio, la carga sintética y el humo.
El paso de Chrome agotó ocho segundos en `Target.createTarget`, antes de navegar.
Los dos logs registran Ubuntu 24.04, imagen `20261116.133.1`, y Node `24.22.3`.
La versión, la ruta resuelta del navegador y el stderr de Chrome no quedaron registrados.
La evidencia acota el fallo a la preparación de Chrome o su canal CDP en el runner;
todavía no distingue un arranque lento de un problema del canal o del ejecutable.

El ajuste confirma CDP con `Browser.getVersion` y un plazo único de 30 segundos.
Los comandos posteriores conservan ocho segundos. El workflow registra ubicación y
versión del ejecutable. El script registra flags, código o señal de salida y fragmentos
reconocidos de stderr de arranque dentro de un búfer de 4096 caracteres. Los diagnósticos
distinguen un error de lanzamiento, un canal cerrado y la salida del proceso. Las
comprobaciones funcionales y el transporte por tuberías se conservan.

| Comando o comprobación | Resultado local |
| --- | --- |
| `node --check scripts/browser_check.mjs` y `node --check scripts/browser_check.test.mjs` | Sintaxis correcta |
| `node --test scripts/browser_check.test.mjs` | 4 pruebas. Ejecutable ausente, salida prematura con filtrado de stderr, cierre del canal y respuesta de preparación seguida del plazo de 8 s. Correctas en macOS con Node 23.11.0 y en la imagen Linux local `node:24-alpine` con Node 24.22.3 |
| Parseo del YAML y `git diff --check` | Correctos |
| `FDH_API_PORT=18000 FDH_WEB_PORT=18080 FDH_EXPECT_SYNTHETIC=1 ./scripts/smoke.sh` | Correcto con la semilla y las imágenes existentes |
| `FDH_BROWSER_URL=http://127.0.0.1:18080 FDH_CHROME_NO_SANDBOX=1 node scripts/browser_check.mjs` | Chrome real `158.0.8127.38` en macOS con Node `23.11.0`, CDP `1.3` listo en 1337 ms. Pasaron catálogo, búsqueda, procedencia, visibilidad, ejecuciones y estados de interfaz. Se registraron avisos locales del asignador y de `CVDisplayLink` |

La validación reutilizó el bundle de E2 y PostgreSQL con la semilla sintética. Se
comprobó el espacio antes de ejecutarla y se prescindió de compilaciones Docker.
La verificación en Ubuntu queda pendiente de la publicación autorizada del commit
de corrección. Si la preparación agota 30 segundos en Ubuntu, el registro permite
diagnosticar el lanzador y el canal en ese entorno.
