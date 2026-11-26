# Tareas: FDH-001 — Descubrimiento y catálogo

**Entrada**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Pruebas**: obligatorias (constitución VIII y FDH-001-NFR-03), aunque la plantilla las trate como opcionales. En cada fase se escriben primero y deben fallar antes de implementar.

**Formato**: `[ID] [P] [US] Descripción con ruta (requisitos; criterios)`. `[P]`: puede ejecutarse a la vez que otras tareas `[P]` de su misma ola, porque toca archivos distintos y no depende de ellas. `FR-NN`, `NFR-NN` y `AC-NN` abrevian `FDH-001-…`.

## Historias

La especificación tiene dos escenarios sin prioridad. Se descomponen así:

| Historia | Escenario | Prioridad | Entrega |
|---|---|---|---|
| US1 Descubrir en Socrata | Persona operadora | P1 | E1 |
| US2 Consultar el catálogo | Persona analista | P1 | E2 |
| US3 Segunda fuente, Data360 | Persona operadora y analista | P2 | E3 |
| US4 Revisar permisos y estados | Persona operadora | P2 | E4 |

## Fase 1: Preparación (E0)

- [X] T001 Crear `backend/pyproject.toml` (paquete `fdh`, Python `>=3.13,<3.14`, licencia Apache-2.0, comando `fdh = "fdh.cli.main:main"`, dependencias de plan.md), comprobar que cada licencia es compatible con Apache-2.0, anotar el resultado en `backend/DEPENDENCIES.md`, generar `backend/uv.lock` y pasar `specs/001-source-discovery/spec.md` a `In Progress` conservando el registro de aprobación (NFR-03)
- [X] T002 Configurar en `backend/pyproject.toml` ruff, mypy estricto, cobertura mínima del 85 % sobre `domain` y `dataplane` y pytest con `asyncio_mode=auto`, marcador `live` excluido por defecto y bloqueo de red salvo el equipo local; probar en `backend/tests/unit/test_network_guard.py` que una conexión externa falla y que asyncio y la base de datos local funcionan (NFR-03; AC-28)
- [X] T003 Crear paquetes en `backend/src/fdh/{domain,controlplane,dataplane/connectors,dataplane/discovery,persistence,api,cli,settings,observability}/__init__.py`, directorios `backend/tests/{unit,contract,integration,api,architecture,live,fixtures/synthetic}/` y una prueba mínima en `backend/tests/unit/test_package.py` (NFR-03)
- [X] T004 [P] Crear `frontend/package.json`, `frontend/package-lock.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json` (estricto), `frontend/eslint.config.js`, `frontend/index.html`, `frontend/src/test/setup.ts`, una estructura inicial en `frontend/src/{App.tsx,main.tsx}` y su prueba `frontend/src/test/app.test.tsx`, con React 19, TypeScript 5.9.3, Vite 8, Vitest y Testing Library; comprobar licencias (FR-05, NFR-03)
- [X] T005 [P] Crear `compose.yaml` (servicios `db` con `postgres:18` fijado por resumen y volumen en `/var/lib/postgresql`, `migrate`, `api`, `web`; puertos publicados solo en `127.0.0.1`; controles de salud; `./config` montado en solo lectura únicamente en `api` y `migrate` con `FDH_CONFIG=/app/config/sources.toml`) `.env.example` sin valores reales, `scripts/check_compose.py` (puertos locales y montaje de solo lectura sobre `docker compose config --format json`) y `scripts/smoke.sh` (salud de la API y del portal) (NFR-01, NFR-03; AC-25, AC-28)
- [X] T006 [P] Crear `backend/Dockerfile` y `backend/.dockerignore`: `python:3.13-slim` fijada por resumen, `uv sync --locked`, usuario sin privilegios y sin configuración incorporada a la imagen (NFR-01)
- [X] T007 [P] Crear `frontend/Dockerfile`, `frontend/.dockerignore` y `frontend/nginx.conf`: nginx sin privilegios fijado por resumen, archivos estáticos, proxy `/api` y `/health` a `api`, validación de `Host` local y cabeceras CSP, `X-Content-Type-Options` y `Referrer-Policy` (NFR-01; AC-25)
- [X] T008 Crear `.github/workflows/ci.yml` con `permissions: contents: read`, disparadores `push` en `**` y `pull_request`, acciones fijadas por SHA y trabajos `backend` (`uv sync --locked`, ruff, formato, mypy, pytest sin red), `integration` (servicio PostgreSQL 18, migraciones), `frontend` (`npm ci`, ESLint, tipos, pruebas, compilación), `compose` (configuración, puertos, montaje, construcción, arranque y humo) y `security` (gitleaks fijado por versión y resumen, bloquea); un commit vacío con `[ci-fail-demo]` en el mensaje hace fallar un paso dedicado (NFR-01, NFR-03; AC-24, AC-28, AC-37)

**Punto de control E0** (tras la Fase 2, de la que depende un entorno ejecutable): `docker compose up` levanta `db`, `migrate`, `api` con `/health` y `web`; los trabajos de CI pasan.

## Fase 2: Fundamentos (bloquea las historias)

- [X] T009 [P] Escribir `backend/tests/architecture/test_import_rules.py` (según la tabla de plan.md: `dataplane.connectors` solo importa `domain` y su contrato) y `backend/tests/architecture/test_openapi_document.py` (validación formal de contracts/openapi.yaml, solo método GET) (FR-04, FR-06, NFR-03; AC-15, AC-34)
- [X] T010 [P] Escribir `backend/tests/unit/test_domain.py`: tabla de `final_status` (0,0,0 → succeeded; con rechazos o fallos, partial si valid > 0 y failed si valid = 0); localizador `invalid` si no es URL HTTPS absoluta con host, no utilizable para extracción; permisos `undetermined` por defecto (FR-03, NFR-02; AC-08, AC-09, AC-10, AC-11, AC-32, AC-35, AC-36)
- [X] T011 [P] Implementar `backend/src/fdh/domain/status.py` con `RunStatus` y `final_status`; `truncated` no es una entrada (FR-03; AC-30)
- [X] T012 [P] Implementar `backend/src/fdh/domain/permissions.py`: `permission` = `allowed|denied|undetermined` (predeterminado `undetermined`), `review_status` = `pending|verified|restricted` (predeterminado `pending`) y la regla de visibilidad «fuente `allowed` y dataset no `restricted`» (NFR-02; AC-27, AC-35)
- [X] T013 [P] Implementar `backend/src/fdh/domain/locators.py`: estado `unverified|invalid`, validación sintáctica sin red y `usable_for_extraction` falso si `invalid` (FR-03; AC-36)
- [X] T014 [P] Implementar en `backend/src/fdh/domain/datasets.py` los tipos `DatasetDates`, `AccessLocator` (tipo abierto), `DeclaredLicense`, `DiscoveredDataset` y `RejectedRecord` de contracts/adapter-contract.md (FR-03; AC-07)
- [X] T015 Implementar `backend/src/fdh/dataplane/connectors/contract.py` (capacidades, contexto sin permisos, solicitud, respuesta, página, `ErrorKind`, `InvalidResponse`, protocolo) y `backend/src/fdh/dataplane/connectors/registry.py` por `platform`, tras T014 (FR-06; AC-21, AC-33)
- [X] T016 [P] Escribir `backend/tests/unit/test_sources_config.py` según contracts/sources-config.md: `source_id` único `^[a-z0-9-]+$`; HTTPS y host permitido; `1 ≤ page_size ≤ 100`; `1 ≤ max_pages ≤ 100`; `attempt_timeout_s > 0`; `0 ≤ max_retries ≤ 3`; permiso distinto de `undetermined` exige `declared_by`, `declared_on` y `evidence`; licencia, URL de condiciones y fecha de revisión desconocidas si se omiten; claves desconocidas rechazadas sin solicitudes (FR-01, FR-06, NFR-02; AC-02, AC-26, AC-33, AC-35)
- [X] T017 Implementar `backend/src/fdh/settings/sources.py` (TOML con `tomllib` y valores 100, 5, 10 s, 3, 60 s) y `backend/src/fdh/settings/env.py` (base de datos y hosts por entorno, sin secretos en logs), tras T015 (FR-01, FR-06, NFR-01; AC-02, AC-33)
- [X] T018 Crear `config/sources.toml` solo con `co-datos-gov` según contracts/sources-config.md, con evidencia del permiso `allowed`, atribución, licencia, URL de condiciones, condiciones de acceso y redistribución y consultas, tras T017 (FR-01, NFR-02; AC-01, AC-26)
- [X] T019 [P] Implementar `backend/src/fdh/observability/logging.py` (JSON a `stderr`, `run_id` por contexto, ocultación de claves sensibles, sin cuerpos ni cabeceras) y `backend/tests/unit/test_logging.py` con credenciales ficticias (NFR-01; AC-24)
- [X] T020 Implementar `backend/src/fdh/persistence/models.py` y `backend/src/fdh/persistence/session.py` con las tablas de data-model.md, incluidas: licencia y condiciones por fuente; único (`source_id`, `external_id`); `title` obligatorio; `review_status` `pending` por defecto; `extraction_permission` y `redistribution_permission` `undetermined` por defecto; localizador único (`dataset_id`, `kind`, `url`, `source_field`); observación única (`dataset_id`, `run_id`, `query_index`); `publication_evidence_url`, `publication_declared_by` y `publication_declared_on` obligatorios si `metadata_publication` no es `undetermined`; bitácora con `evidence` y `decided_by` obligatorios (FR-02, FR-03, NFR-02; AC-06, AC-26)
- [X] T021 Crear `backend/alembic.ini`, `backend/migrations/env.py` y `backend/migrations/versions/0001_initial.py` con extensión `unaccent`, enumeraciones, restricciones e índices de data-model.md (GIN en `category_keys`), tras T020 (FR-03)
- [X] T022 Escribir `backend/tests/integration/conftest.py` (base de datos de pruebas PostgreSQL real, limpia por prueba) y `backend/tests/integration/test_migrations.py` (`upgrade head`, `alembic check`, unicidad y obligatoriedad), tras T021 (FR-02, NFR-03; AC-06, AC-28)
- [X] T023 [P] Definir en `backend/src/fdh/controlplane/ports.py` las interfaces de repositorios de fuentes, catálogo, ejecuciones, consultas y decisiones, e implementar `backend/src/fdh/controlplane/sources.py`: plan de sincronización puro que declara `undetermined` toda fuente retirada de la configuración y nunca toca datos de datasets, tras T014 y T017 (FR-02, FR-03, NFR-02; AC-27, AC-35)
- [X] T024 Implementar `backend/src/fdh/persistence/sources.py` (aplica el plan de sincronización y la bitácora en una transacción) y `backend/src/fdh/cli/main.py` con `fdh config check` (sin red ni base de datos) y `fdh sources sync` (solo base de datos, sin solicitudes externas), la aplicación mínima `backend/src/fdh/api/app.py` con `/health` y su prueba, con `backend/tests/integration/test_sources_sync.py`: revocación efectiva sin descubrimiento ni red y restricciones de datasets intactas, tras T020 a T023 (FR-01, FR-06, NFR-02; AC-02, AC-27, AC-33, AC-35)

**Punto de control**: contratos, dominio y esquema integrados. Desde aquí pueden abrirse espacios paralelos.

**E0 verificada el 2026-11-26**: [evidencia](../../research/experiments/fdh-001-validation/README.md). US1 no se ha iniciado.

## Fase 3: US1 — Descubrir en Socrata (P1, E1) 🎯

**Objetivo**: `fdh discover --source co-datos-gov` guarda datasets, procedencia y ejecuciones.
**Prueba independiente**: con respuestas sintéticas y PostgreSQL real, dos ejecuciones no duplican y los estados siguen la regla.

### Pruebas e investigación

- [X] T025 [US1] Leer la referencia oficial de Socrata Discovery API (parámetros, `scroll_id`, límites y condiciones) y registrar fuente, fecha y hallazgos en `research/sources/colombia/socrata/README.md`; si contradice la decisión D05 de `specs/001-source-discovery/research.md`, actualizarla antes de T032; si no puede leerse, documentarlo y mantener el cursor observado (constitución II; NFR-03; AC-29)
- [X] T026 [P] [US1] Crear respuestas sintéticas identificadas como tales en `backend/tests/fixtures/synthetic/socrata/` para los casos de la suite de contrato, sin datos reales (NFR-03; AC-28)
- [X] T027 [US1] Escribir `backend/tests/contract/suite.py` (casos de «Suite de contrato») y `backend/tests/contract/test_socrata.py`: solo datasets de `www.datos.gov.co`, 100 por página, `scroll_id`, descarte de `owner`, `creator` y `contact_email`, y correspondencia de campos, tras T026 (FR-01, FR-03, FR-06; AC-01, AC-07, AC-21, AC-33, AC-34, AC-36)
- [X] T028 [P] [US1] Escribir `backend/tests/unit/test_http_executor.py` con `httpx.MockTransport` y reloj falso: plazo total de 10 s por intento incluida la lectura, 4 intentos máximos, esperas de 1, 2 y 4 s nunca menores que `Retry-After`, sin reintento si supera 60 s, un solo intento en 400, 401, 403 y 404, host no permitido, redirección rechazada y respuesta mayor de 10 MB (NFR-01; AC-22, AC-23, AC-24)
- [X] T029 [P] [US1] Escribir `backend/tests/unit/test_engine.py` con adaptador y repositorios falsos: máximo 5 páginas por consulta, `truncated` y total por consulta, fallo de una consulta que no detiene las demás, `Retry-After` excesivo que detiene la ejecución, estados con válidos, rechazados y vacíos, un dataset repetido contado una sola vez en `created`, `updated` o `unchanged`, y errores sanitizados (FR-01, FR-03; AC-01, AC-02, AC-08, AC-09, AC-10, AC-11, AC-30, AC-32)
- [X] T030 [P] [US1] Escribir `backend/tests/integration/test_catalog_persistence.py`: deduplicación e historial entre consultas, actualización sin duplicar, conservación de primera observación y ausentes, mismo identificador en dos fuentes, rechazo de duplicado, conservación de datos tras fallo, reemplazo y revalidación de localizadores, permisos humanos intactos y fuente con URL y fecha de verificación (FR-02, FR-03, NFR-02; AC-03, AC-04, AC-05, AC-06, AC-07, AC-09, AC-26, AC-36)

### Implementación

- [X] T031 [P] [US1] Implementar `backend/src/fdh/dataplane/discovery/retry.py` y `backend/src/fdh/dataplane/discovery/http.py` (httpx asíncrono, `asyncio.timeout` por intento, hosts permitidos, HTTPS, sin redirecciones, límite de 10 MB, reloj y espera inyectables) (NFR-01; AC-22, AC-23)
- [X] T032 [US1] Implementar `backend/src/fdh/dataplane/connectors/socrata/adapter.py` y registrarlo en `registry.py`, con la correspondencia y el cursor de contracts/adapter-contract.md, tras T025 y T027 (FR-01, FR-03, FR-06; AC-01, AC-07, AC-21)
- [X] T033 [P] [US1] Implementar `backend/src/fdh/persistence/hashing.py`: huella de metadatos y claves `casefold` de categorías y temas, con pruebas en `backend/tests/unit/test_hashing.py` (FR-02, FR-03, FR-04; AC-04, AC-13)
- [X] T034 [US1] Implementar `backend/src/fdh/persistence/catalog.py`: inserción o actualización por (`source_id`, `external_id`), huella de metadatos, `category_keys`, localizadores y observaciones por transacción de página, sin modificar revisión, permisos ni condiciones, tras T033 (FR-02, FR-03; AC-03, AC-04, AC-05, AC-07, AC-36)
- [X] T035 [P] [US1] Implementar `backend/src/fdh/persistence/runs.py`: crear, acumular conteos y consultas, bloqueo consultivo por fuente y cierre de ejecuciones abandonadas con error `interrupted` (FR-03; AC-08, AC-09)
- [X] T036 [US1] Implementar `backend/src/fdh/dataplane/discovery/engine.py` según los 8 pasos de plan.md, tras T031, T034 y T035 (FR-01, FR-02, FR-03; AC-08, AC-09, AC-10, AC-11, AC-30, AC-32)
- [X] T037 [US1] Implementar `backend/src/fdh/cli/discover.py` y registrar en `main.py` `discover` y `runs list` (`--limit` de 1 a 100, predeterminado 20), tras T032 y T036 (FR-01, FR-03; AC-01, AC-02, AC-09)
- [X] T038 [US1] Escribir `backend/tests/integration/test_discover_cli.py`: comando completo con transporte sintético y PostgreSQL, códigos de salida, repetición sin duplicados y cambio de configuración sin cambiar código, tras T037 (FR-01, FR-02; AC-02, AC-04, AC-19)

**Punto de control E1**: descubrimiento Socrata demostrable por línea de comandos.

**E1 ejecutada el 2026-11-26**: [evidencia](../../research/experiments/fdh-001-validation/README.md#e1-descubrimiento-en-socrata-t025-a-t038). De T067 solo se adelantó la prueba en vivo de Socrata; sigue abierta. US2 no se ha iniciado.

## Fase 4: US2 — Consultar el catálogo (P1, E2) 🎯

**Objetivo**: API y portal de solo lectura con búsqueda, detalle, procedencia y ejecuciones.
**Prueba independiente**: con datos sintéticos cargados en PostgreSQL, API y portal cumplen filtros, visibilidad y estados.

### Pruebas

- [ ] T039 [P] [US2] Escribir `backend/tests/api/test_openapi_contract.py`: rutas, parámetros, límites y respuestas generados coinciden con contracts/openapi.yaml y solo existe el método GET (FR-04; AC-15)
- [ ] T040 [P] [US2] Escribir `backend/tests/api/test_datasets.py`: `page` de 1 a 10000, `page_size` de 1 a 100 con 20 por defecto y 422 al exceder; `q` y filtros de máximo 200 caracteres, sin tildes, comodines escapados; categoría o tema; detalle completo con licencia y condiciones de la fuente y las 20 observaciones más recientes con su total; procedencia paginada; 404; ocultación de fuentes `undetermined` o `denied` y de `restricted`; `pending` identificado; atribución, varias licencias, externas y ausentes; conexión de solo lectura (FR-04, NFR-02; AC-12, AC-13, AC-14, AC-15, AC-26, AC-27, AC-31)
- [ ] T041 [P] [US2] Escribir `backend/tests/api/test_runs.py`: lista y detalle con estado, conteos, truncamiento y total por consulta, errores sanitizados; `partial` y `failed` nunca como éxito; `/health` y 503 (FR-03, FR-04; AC-09, AC-15, AC-30)
- [ ] T042 [P] [US2] Escribir `frontend/src/test/catalog.test.tsx` y `frontend/src/test/detail.test.tsx`: cargando, vacío y fallido distintos; mismos registros que la respuesta de la API; licencias, requisito de cita, atribución, permisos, revisión, procedencia, verificación, «desconocido», enlaces solo HTTPS y contenido como texto (FR-03, FR-05, NFR-02; AC-16, AC-17, AC-18, AC-31, AC-36)
- [ ] T043 [P] [US2] Escribir `frontend/src/test/runs.test.tsx`: cuatro estados distinguibles, truncamiento visible y estados cargando, vacío y fallido (FR-05; AC-16, AC-17, AC-30)

### Implementación

- [ ] T044 [US2] Implementar `backend/src/fdh/persistence/queries.py`: la regla de visibilidad en un único punto, búsqueda `unaccent` e `ILIKE`, filtro por `category_keys`, paginación, proveedores, categorías, procedencia y ejecuciones (FR-04, NFR-02; AC-12, AC-13, AC-27)
- [ ] T045 [P] [US2] Implementar `backend/src/fdh/api/schemas.py` según contracts/openapi.yaml, incluida la procedencia reciente del detalle y la licencia de la fuente (FR-04; AC-14, AC-31)
- [ ] T046 [US2] Ampliar `backend/src/fdh/api/app.py`: validación de `Host`, sin CORS, transacciones de solo lectura, errores sanitizados 404, 422 y 503 y registro de rutas, tras T045 (FR-04, NFR-01; AC-15, AC-25)
- [ ] T047 [P] [US2] Implementar `backend/src/fdh/api/routes/datasets.py` (datasets, detalle con procedencia reciente, procedencia paginada, proveedores, categorías), tras T044 y T046 (FR-04, NFR-02; AC-12, AC-13, AC-14, AC-27, AC-31)
- [ ] T048 [P] [US2] Implementar `backend/src/fdh/api/routes/runs.py`, tras T044 y T046 (FR-04; AC-15, AC-30)
- [ ] T049 [P] [US2] Generar `frontend/src/api/schema.d.ts` desde contracts/openapi.yaml y crear `frontend/src/api/client.ts` y `frontend/src/api/queries.ts`; añadir el script `api:check` en `frontend/package.json` (FR-05)
- [ ] T050 [US2] Implementar componentes sin red ni enrutador en `frontend/src/components/` (`StateView`, `DatasetCard`, `LicenseList`, `Attribution`, `LocatorList`, `SafeLink`, `RunStatusBadge`, `Pagination`, `Filters`), accesibles por teclado (FR-03, FR-05, NFR-02; AC-16, AC-31, AC-36)
- [ ] T051 [P] [US2] Implementar `frontend/src/pages/CatalogPage.tsx`, tras T049 y T050 (FR-05; AC-16, AC-17, AC-31)
- [ ] T052 [P] [US2] Implementar `frontend/src/pages/DatasetPage.tsx`, tras T049 y T050 (FR-05, NFR-02; AC-18, AC-31)
- [ ] T053 [P] [US2] Implementar `frontend/src/pages/RunsPage.tsx`, tras T049 y T050 (FR-05; AC-17, AC-30)
- [ ] T054 [US2] Implementar `frontend/src/main.tsx`, `frontend/src/App.tsx` (rutas y diseño), tras T051 a T053 (FR-05; AC-17)
- [ ] T055 [US2] Crear `backend/tests/fixtures/synthetic/seed.py` (datos sintéticos identificados), ampliar `scripts/smoke.sh` con el catálogo sembrado y añadir a `.github/workflows/ci.yml` la comprobación de deriva de OpenAPI y `api:check`, tras T047, T048 y T054 (FR-04, FR-05, NFR-01, NFR-03; AC-25, AC-28, AC-37)

**Punto de control E2**: primer corte utilizable; descubrir en Socrata y verlo en API y portal.

## Fase 5: US3 — World Bank Data360 (P2, E3)

**Objetivo**: segunda fuente sin cambiar el núcleo.
**Prueba independiente**: la suite de contrato pasa y sus registros aparecen en la misma API y portal.

- [ ] T056 [US3] Confirmar y completar en `research/sources/international/world-bank/README.md` la documentación oficial, las condiciones y las pruebas en vivo de Data360, y buscar un patrón documentado de URL de dataset; si Data360 deja de ser viable, detener y solicitar aprobación de alternativa (FR-06, NFR-03; AC-20, AC-29)
- [ ] T057 [P] [US3] Crear respuestas sintéticas identificadas en `backend/tests/fixtures/synthetic/data360/` (NFR-03; AC-28)
- [ ] T058 [US3] Escribir `backend/tests/contract/test_data360.py` sobre la suite: `POST` con `type eq 'dataset'` y `count`, `skip` ≤ 100000, rechazo de otros tipos, varias categorías y temas, licencias múltiples, externas y ausentes, localizador HTTP conservado, `official_url` y `publisher` desconocidos, tras T027 y T057 (FR-03, FR-04, FR-06; AC-07, AC-21, AC-31, AC-33, AC-34, AC-36)
- [ ] T059 [US3] Implementar `backend/src/fdh/dataplane/connectors/data360/adapter.py` y registrarlo en `registry.py`, tras T056 y T058, sin modificar `domain`, `controlplane`, `persistence`, `api` ni `frontend` (FR-06; AC-21)
- [ ] T060 [US3] Añadir `int-worldbank-data360` a `config/sources.toml` según contracts/sources-config.md, tras T059 (FR-06, NFR-02; AC-21, AC-26)
- [ ] T061 [US3] Escribir `backend/tests/integration/test_two_sources.py`: ambas fuentes con transporte sintético, mismo identificador en dos fuentes y mismos registros publicables por la API, tras T047 y T060 (FR-01, FR-02, FR-06; AC-06, AC-19, AC-21)

**Punto de control E3**: dos fuentes en el mismo catálogo.

## Fase 6: US4 — Revisar permisos y estados (P2, E4)

**Objetivo**: una persona registra revisión, permisos y condiciones con evidencia.
**Prueba independiente**: tras restringir un dataset, desaparece de la API; ningún redescubrimiento revierte la decisión.

- [ ] T062 [US4] Escribir `backend/tests/integration/test_reviews.py`: `--evidence`, `--by` y `--on` obligatorios y no vacíos; permisos `allowed|denied|undetermined`; estados `pending|verified|restricted`; bitácora en la misma transacción; restricción que prevalece sobre la fuente `allowed`; metadatos `allowed` que no cambian extracción ni redistribución; ni el redescubrimiento ni `sources sync` la revierten; sin solicitudes externas (NFR-02; AC-27, AC-35)
- [ ] T063 [P] [US4] Implementar `backend/src/fdh/persistence/decisions.py` (solo inserción y actualización del dataset en una transacción) (NFR-02; AC-35)
- [ ] T064 [US4] Implementar `backend/src/fdh/controlplane/review.py`, tras T063 (NFR-02; AC-27, AC-35)
- [ ] T065 [US4] Implementar `backend/src/fdh/cli/dataset.py` y registrar en `main.py` `dataset show`, `review`, `permission` y `conditions` según contracts/cli.md, tras T064 (NFR-02; AC-27, AC-35)

**Punto de control**: gobierno de permisos demostrable.

## Fase 7: Cierre y asuntos transversales (E4)

- [ ] T066 Añadir a `.github/workflows/ci.yml` la auditoría informativa de dependencias con `pip-audit` y `npm audit` (NFR-01, NFR-03; AC-37)
- [ ] T067 [P] Escribir `backend/tests/live/test_live_discovery.py` (marcador `live`, una consulta y una página por fuente) que guarde en `research/sources/` fecha UTC, solicitud, commit, resultado y fallos, sin nombres ni datos personales (FR-01, NFR-03; AC-19, AC-29)
- [ ] T068 [P] Redactar `docs/adr/0009-lovable-integration.md` en estado `Proposed` (decisión D09) y enlazarlo en `docs/adr/README.md` (FR-05)
- [ ] T069 [P] Documentar arranque, pruebas, comandos y configuración en `README.md` y `docs/engineering/local-development.md`, incluidos los espacios de trabajo de plan.md (NFR-03; AC-28)
- [ ] T070 Ejecutar `quickstart.md` desde un clon limpio y registrar comandos, commit, salidas y desviaciones en `research/experiments/fdh-001-validation/README.md` (NFR-01, NFR-03; AC-25, AC-28)
- [ ] T071 Ejecutar la validación en vivo de ambas fuentes, comprobar los mismos registros en API y portal y registrar el resultado real en `research/experiments/fdh-001-validation/README.md`, tras T067 (FR-01, NFR-03; AC-19, AC-29)
- [ ] T072 Publicar un commit vacío con `[ci-fail-demo]`, comprobar en GitHub que la ejecución falla de forma visible y que la siguiente vuelve a pasar, y anotar ambos enlaces en `research/experiments/fdh-001-validation/README.md` (NFR-03; AC-37)
- [ ] T073 Crear la matriz requisito → criterio → tarea → prueba → evidencia en `specs/001-source-discovery/checklists/traceability.md`, declarar lo no ejecutado y preparar el handoff para la revisión humana por PR, que solo se abre con autorización (NFR-03)

## Dependencias

```text
Fases 1 y 2 (E0) ─────┬─► US1 (E1) ─┬─► US4 (E4) ──┐
                      ├─► US2 (E2)  │              ├─► Cierre
                      └─► US3 adaptador ─► US3 integración (E3) ┘
```

| Historia | Depende de | Para integrarse |
|---|---|---|
| US1 | Fase 2 | — |
| US2 | Fase 2; usa datos sintéticos | E2 completa requiere US1 |
| US3 | T027 (suite) para el adaptador | T061 requiere US1 y T047 |
| US4 | T024, T034 | Se verifica también por la API de US2 |

Dentro de cada historia: pruebas, implementación e integración. Las tareas con «tras» indican dependencias directas.

## Trabajo en paralelo

Cada línea usa su propio espacio `git worktree add --detach` (sin ramas); un único integrador aplica con `cherry-pick` y publica.

| Ola | Espacio | Tareas | Archivos propios | Requiere |
|---|---|---|---|---|
| 0 | principal | T001–T003, T008 | proyecto backend y CI | T004 a T007 para completar T008 |
| 0 | `fdh-ws-web-base` | T004, T007 | `frontend/` base | — |
| 0 | `fdh-ws-infra` | T005, T006 | Compose y Dockerfile backend | T001 para T006 |
| 1 | principal | T009–T024 | dominio, contrato, configuración, esquema | Ola 0 |
| 2 | `fdh-ws-network` | T028, T031 | `dataplane/discovery/{http,retry}.py` | Ola 1 |
| 2 | `fdh-ws-socrata` | T025–T027, T032 | `connectors/socrata/`, suite | Ola 1 |
| 2 | `fdh-ws-ingest` | T029, T030, T033–T036 | `persistence/{hashing,catalog,runs}.py`, motor | Ola 1; T031 antes de T036 |
| 2 | `fdh-ws-api` | T039–T041, T044–T048 | `api/`, `persistence/queries.py` | Ola 1 |
| 2 | `fdh-ws-portal` | T042, T043, T049–T054 | `frontend/src/` | Ola 0; contrato OpenAPI |
| 3 | `fdh-ws-data360` | T056–T059 | `connectors/data360/` | T027 |
| 3 | `fdh-ws-review` | T062–T065 | `persistence/decisions.py`, revisión, CLI de datasets | T024, T034 |
| 3 | principal | T037, T038, T055, T060, T061 | integración | Olas 2 y 3 |
| 4 | varios | T067–T069 | independientes | Integración |
| 4 | principal | T066, T070–T073 | CI y validación | Todo lo anterior |

Cada línea entrega su módulo; los registros en archivos compartidos los hace el integrador al fusionar. Archivos compartidos: `registry.py` (T015, T032, T059), `cli/main.py` (T024, T037, T065), `persistence/models.py` (T020), `config/sources.toml` (T018, T060), `ci.yml` (T008, T055, T066), `frontend/package.json` (T004, T049) y `backend/pyproject.toml` (T001, T002).

## Estrategia

1. **E0**: Fases 1 y 2; la Fase 2 en una sola línea.
2. **Primer MVP utilizable (E1 + E2)**: US1 y US2, en paralelo; detenerse y validar con datos reales.
3. **E3**: Data360.
4. **E4**: revisión de permisos y cierre. FDH-001 solo está completa con las cuatro historias.

No marcar una tarea sin su prueba o evidencia. Registrar lo no ejecutado. Publicar únicamente en la rama de desarrollo con autorización.
