# Guía de validación de FDH-001

**Estado: E0, E1 y E2 implementadas.** El descubrimiento de Socrata alimenta el catálogo.
La API y el portal permiten buscar datasets, consultar su procedencia y revisar ejecuciones y
métricas. Los escenarios de Data360 y el comando de revisión de permisos corresponden a E3 y E4.
Consulta los contratos de [CLI](contracts/cli.md), [configuración](contracts/sources-config.md) y
[API](contracts/openapi.yaml), y el [modelo de datos](data-model.md).

## Requisitos previos
Docker con Compose en ejecución, [uv](https://docs.astral.sh/uv/) y Git. Node 24 solo si se quiere trabajar en el portal fuera de Docker. La primera instalación de dependencias e imágenes necesita red; las pruebas ordinarias, no. Reservar unos 3 GB libres.

## Preparación desde un clon limpio

```bash
cp .env.example .env                       # escribir una contraseña en POSTGRES_PASSWORD
docker compose up --detach --build --wait  # db, migrate, api y web
./scripts/smoke.sh
docker compose run --rm api fdh config check
docker compose run --rm api fdh sources sync
```

Esperado: la prueba de humo pasa, `http://127.0.0.1:8000/health` responde `{"status":"ok"}` y `http://127.0.0.1:8080` muestra «Servicio disponible.».

## Pruebas

Backend, con la base de datos de Compose en marcha (cada prueba crea y elimina su propia base):

```bash
cd backend
uv sync --locked
export FDH_DB_PASSWORD="$(sed -n 's/^POSTGRES_PASSWORD=//p' ../.env)"
uv run pytest                      # todas; conexiones externas bloqueadas
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

Sin base de datos, desde `backend/`:

```bash
uv run pytest tests/unit tests/contract tests/architecture \
  tests/api/test_health.py tests/api/test_errors.py tests/api/test_openapi_contract.py
```

Portal, con Node 24 (`npm ci && npm run lint && npm test && npm run build` en `frontend/`) o solo con Docker:

```bash
docker build --target build -t fdh-web-check frontend
docker run --rm --network none fdh-web-check sh -c "npm run lint && npm run typecheck && npm test"
```

Si un puerto está ocupado, definir `FDH_DB_PORT`, `FDH_API_PORT` o `FDH_WEB_PORT` en `.env`; para las pruebas del backend, exportar también `FDH_DB_PORT`.

## Contrato, catálogo sintético y Chrome (E2)

Para verificar los tipos del portal, ejecuta `FDH_API_PYTHON=../backend/.venv/bin/python npm run api:check`
desde `frontend/` después de preparar el entorno de backend. Si cambia el contrato aprobado,
regenera las declaraciones con `cd backend && uv run python ../scripts/generate_api_types.py`.

En una instancia de Compose desechable, con la migración aplicada y sin datos reales:

```bash
docker compose exec -T api python - < backend/tests/fixtures/synthetic/seed.py
FDH_EXPECT_SYNTHETIC=1 ./scripts/smoke.sh
node scripts/browser_check.mjs
```

El script usa Chrome instalado localmente. `CHROME_BIN` permite indicar su ruta.
`FDH_BROWSER_URL` permite verificar otro portal local. El portal y la API deben compartir origen.
Para integrar Visual Pipeline Studio, consume el contrato HTTP publicado en `/openapi.json`
desde el proyecto independiente de Lovable, mediante un proxy de mismo origen cuando corresponda.

## Descubrimiento en Socrata (E1)

Envía solicitudes reales a `api.us.socrata.com`: dos consultas de hasta cinco páginas.

```bash
docker compose build api                                   # tras actualizar el código
docker compose up --detach --wait
docker compose run --rm api fdh discover --source co-datos-gov
docker compose run --rm api fdh runs list
docker compose exec db psql -U fdh -d fdh -c "select count(*), count(distinct (source_id, external_id)) from datasets"
```

La salida `stdout` resume cada ejecución; los logs JSON van a `stderr`. Códigos de salida en el [contrato de la CLI](contracts/cli.md).

## Escenarios

| # | Pasos | Resultado esperado | Criterios |
|---|---|---|---|
| 1 | `docker compose run --rm api fdh config check` | Código 0, sin red | AC-02 |
| 2 | `docker compose run --rm api fdh discover --all` | Una ejecución por fuente; códigos 0, 3 o 4 según el resultado real | AC-01, AC-19, AC-21 |
| 3 | `GET /api/v1/datasets` y el portal | Los mismos registros, con atribución, licencias y estado `pending` | AC-17, AC-19, AC-31 |
| 4 | Repetir el escenario 2 | El total no crece con las mismas respuestas; nuevas ejecuciones e historial | AC-04 |
| 5 | Filtrar por texto, proveedor y categoría; pedir `page_size=101` | Filtros correctos; 422 | AC-12, AC-13 |
| 6 | Revisar la pantalla de ejecuciones | Estados, conteos y truncamiento visibles | AC-30 |
| 7 | `fdh dataset review ... --status restricted` | El dataset desaparece de búsqueda y detalle (404) | AC-27 |
| 8 | Cambiar `metadata_publication` de una fuente a `undetermined` y ejecutar `fdh sources sync`, sin descubrir | Sus datasets dejan de mostrarse, aun sin red externa | AC-27 |
| 9 | Detener `api` y recargar el portal | Estado fallido, distinto de vacío | AC-16 |
| 10 | `docker compose config` | Puertos publicados solo en `127.0.0.1` | AC-25 |

Tras el escenario 8, restaurar la configuración y volver a sincronizar.

## Evidencia en vivo

```bash
cd backend && uv run pytest -m live
```

Registra fecha UTC, solicitudes, commit y resultado, incluidos los fallos, en `research/sources/` (AC-19, AC-29). No guarda datasets, nombres ni datos personales. Un fallo del proveedor se documenta como fallo.

## Integración continua
Publicar en la rama de desarrollo ejecuta el flujo `ci`; un fallo debe verse en GitHub (AC-37).

## Reinicio
`docker compose down` conserva los datos; `docker compose down -v` los elimina.
