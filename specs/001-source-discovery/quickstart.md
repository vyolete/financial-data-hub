# Guía de validación de FDH-001

Comprueba el MVP. **Estado: solo E0 está implementado.** Funcionan la preparación, las pruebas, `fdh config check`, `fdh sources sync`, `/health` y la página inicial del portal. Los escenarios 2 a 9 requieren entregas posteriores. Contratos: [CLI](contracts/cli.md), [configuración](contracts/sources-config.md), [API](contracts/openapi.yaml); datos: [modelo](data-model.md).

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

Sin base de datos: `uv run pytest tests/unit tests/contract tests/architecture tests/api`.

Portal, con Node 24 (`npm ci && npm run lint && npm test && npm run build` en `frontend/`) o solo con Docker:

```bash
docker build --target build -t fdh-web-check frontend
docker run --rm --network none fdh-web-check sh -c "npm run lint && npm run typecheck && npm test"
```

Si un puerto está ocupado, definir `FDH_DB_PORT`, `FDH_API_PORT` o `FDH_WEB_PORT` en `.env`; para las pruebas del backend, exportar también `FDH_DB_PORT`.

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
cd backend && uv run pytest -m live --enable-socket
```

Registra fecha UTC, solicitudes, commit y resultado, incluidos los fallos, en `research/sources/` (AC-19, AC-29). No guarda datasets, nombres ni datos personales. Un fallo del proveedor se documenta como fallo.

## Integración continua
Publicar en la rama de desarrollo ejecuta el flujo `ci`; un fallo debe verse en GitHub (AC-37).

## Reinicio
`docker compose down` conserva los datos; `docker compose down -v` los elimina.
