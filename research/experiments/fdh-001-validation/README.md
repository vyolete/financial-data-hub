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
