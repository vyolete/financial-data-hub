# Guía de validación de FDH-001

Describe cómo comprobar el MVP **una vez implementado**. Hoy no existe código: ningún comando de esta guía se ha ejecutado. Contratos: [CLI](contracts/cli.md), [configuración](contracts/sources-config.md), [API](contracts/openapi.yaml); datos: [modelo](data-model.md).

## Requisitos previos
Docker con Compose en ejecución, uv, Node 24 y Git. La instalación de dependencias e imágenes necesita red; las pruebas ordinarias, no.

## Preparación desde un clon limpio

```bash
cp .env.example .env            # definir POSTGRES_PASSWORD
docker compose up -d --build    # db, migrate, api, web
```

Esperado: `http://127.0.0.1:8000/health` responde `ok` y `http://127.0.0.1:8080` muestra el catálogo en estado vacío.

## Pruebas sin red

```bash
docker compose up -d db
cd backend && uv sync --locked && uv run pytest        # excluye las pruebas en vivo
cd ../frontend && npm ci && npm test && npm run build
```

Esperado: todo en verde con conexiones externas bloqueadas (AC-28, AC-34).

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
