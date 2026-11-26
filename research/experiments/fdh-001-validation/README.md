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
