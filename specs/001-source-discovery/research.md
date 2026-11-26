# Investigación de FDH-001

Pruebas en vivo ejecutadas el 2026-11-26 (UTC). Los detalles y la evidencia viven en `research/`.

| Tema | Resultado | Evidencia |
|---|---|---|
| Socrata Discovery API, `www.datos.gov.co` | Accesible; paginación con `offset` y cursor, errores y metadatos observados. Referencia oficial revisada el 2026-11-26 | [informe](../../research/sources/colombia/socrata/README.md) |
| World Bank Data360 | Accesible; elegida para FR-06 ([ADR-0008](../../docs/adr/0008-world-bank-data360.md)) | [informe](../../research/sources/international/world-bank/README.md) |
| World Bank Data Catalog API | No utilizable en las pruebas: HTTP 429 persistente | [informe](../../research/sources/international/world-bank/README.md) |
| World Bank Indicators API | Accesible; candidata para extracción en FDH-002 y FDH-003. Su código de indicador no es único entre fuentes | [informe](../../research/sources/international/world-bank/README.md) |
| Contrato común de descubrimiento | La propuesta se concreta en el [contrato del plan](contracts/adapter-contract.md) | [propuesta](../../research/experiments/discovery-probe/discovery-contract-proposal.md) |
| Permisos de publicación | `allowed` declarado para ambas fuentes y recogido en la especificación aprobada | [inventario](../../research/sources/inventory.md) |

## Pendiente
- Revisión humana de las licencias externas y ausentes de Data360 antes de extraer datos.
- Decidir si se usa un app token de Socrata, recomendado por su referencia.
- Verificar si existe un patrón documentado de URL de página de dataset en Data360.
- **LAB-01**: un informe anterior registró cero datasets en Socrata. Las pruebas actuales obtuvieron resultados; la causa del informe anterior sigue sin determinar.

## Campos de Data360 para URL y publicador
Comprobación del 2026-11-26 (UTC) con el repositorio en `6452d44`: `python3 -I research/experiments/discovery-probe/data360_links.py`. [Evidencia](../../research/sources/international/world-bank/evidence/links-2026-11-26T013930Z.json), 2 solicitudes, 174 datasets.

- Cada dataset declara exactamente un enlace en `links[]`, sin tipo, que apunta a sitios del proveedor de los datos (FMI, FAO, OCDE, World Bank y otros). Ninguno contiene el identificador del dataset.
- `api_explorer_link` apunta en los 174 casos a `http://datacatalog.worldbank.org`, sin identificador y sin HTTPS.
- `api_link`, `json_link` y `csv_link` son HTTPS.
- `sources[].organization` tiene 175 valores; `sources[].uri`, 171. `authoring_entity` no tiene valores.

## Decisiones del plan (Fase 0)

Versiones consultadas en PyPI, npm, nodejs.org, Docker Hub y GitHub el 2026-11-26 (UTC). Los archivos de bloqueo fijan las versiones exactas.

### D01. Entorno de ejecución
- **Decisión**: Python 3.13, uv, imagen `python:3.13-slim`; Node 24 LTS; PostgreSQL 18.
- **Razón**: versiones con soporte vigente y compatibles con las dependencias elegidas.
- **Alternativas**: Python 3.14 (algunas dependencias aún no lo declaran); Node 26 LTS (más reciente; se adoptará cuando las herramientas lo prueben).

### D02. Backend
- **Decisión**: FastAPI 0.165, Pydantic 2.14, pydantic-settings, Uvicorn, SQLAlchemy 2.1 asíncrono, Alembic, asyncpg. CLI con `argparse` y configuración TOML con `tomllib`.
- **Razón**: un solo modelo asíncrono para red y base de datos; la biblioteca estándar cubre CLI y configuración.
- **Alternativas**: psycopg 3 (licencia LGPL-3.0; asyncpg es Apache-2.0 y evita revisar compatibilidad); Typer (dependencia innecesaria).

### D03. Cliente HTTP y plazo por intento
- **Decisión**: httpx asíncrono; cada intento completo, incluida la lectura del cuerpo, dentro de `asyncio.timeout`.
- **Razón**: los tiempos de espera de los clientes aplican por operación de red; una prueba tardó 11,7 s con un límite de 10 s por operación. `MockTransport` permite pruebas sin red.
- **Alternativas**: aiohttp (mantenimiento más reciente); se podrá sustituir porque solo el ejecutor lo usa.
- **Riesgo**: la última versión de httpx (0.28.1) es de diciembre de 2024.

### D04. Configuración y administración de permisos
- **Decisión**: la fuente (permiso de metadatos, atribución, consultas y límites) se declara en `config/sources.toml`; el estado de revisión y los permisos de cada dataset se cambian con un comando local y quedan en una bitácora.
- **Razón**: las fuentes son pocas y revisables en Git; los datasets se descubren dinámicamente.
- **Alternativas**: todo en archivo (inmanejable para cientos de datasets); todo en comandos (se pierde la revisión de la configuración).

### D05. Paginación de Socrata
- **Decisión**: cursor `scroll_id`, sin `order`.
- **Razón**: recorrió 145 resultados distintos; con `offset` se observó un registro repetido y hay un tope de 10000.
- **Alternativas**: `offset`.
- **Confirmación** (2026-11-26, T025): la [referencia oficial](../../research/sources/colombia/socrata/README.md#referencia-oficial-de-la-discovery-api) documenta `scroll_id` y su incompatibilidad con `order` y `offset`.

### D06. URL oficial, publicador y fuentes de datos en Data360
- **Decisión**: `official_url` y `publisher` quedan desconocidos. Los enlaces se guardan como localizadores y `sources[].organization` como fuentes de los datos para la atribución.
- **Razón**: ningún campo identifica la página del dataset ni su publicador; construir una URL o elegir un publicador sería inferir.
- **Alternativas**: usar `links[]` como URL oficial (apunta a terceros); construir la URL con el identificador (no verificada).

### D07. Categorías y filtro
- **Decisión**: arreglos textuales de categorías y temas, más un arreglo de claves en minúsculas (`casefold`) para filtrar; el filtro compara la clave completa.
- **Razón**: conserva los originales y une variantes de mayúsculas observadas.

### D08. Búsqueda por texto
- **Decisión**: `ILIKE` sobre título y descripción con la extensión `unaccent`.
- **Razón**: suficiente para el volumen del MVP e insensible a tildes.
- **Alternativas**: búsqueda de texto completo o motor externo (innecesarios).

### D09. Portal y Lovable
- **Decisión**: SPA con React 19, Vite 8, TypeScript 5.9, React Router y TanStack Query, servida como archivos estáticos por nginx, con proxy `/api` al backend. Cliente generado desde OpenAPI.
- **Razón**: cumple «sin backend alternativo» y no añade un proceso de servidor.
- **Lovable**: según su [FAQ](https://docs.lovable.dev/introduction/faq), los proyectos nuevos desde mayo de 2026 usan TanStack Start con renderizado en servidor, sin elegir otro stack, y Git no importa repositorios. Su [integración con GitHub](https://docs.lovable.dev/integrations/github) crea un repositorio nuevo y pide escritura en contenido, flujos de trabajo y administración. Por tanto **no se conecta a este repositorio**: se usa para prototipar aparte y el código se incorpora mediante commits revisados. Los componentes de presentación no dependen del enrutador ni de la red para poder trasladarse.
- **Alternativas**: TanStack Start en este repositorio (introduce un servidor Node y funciones de servidor, contrarias al principio III sin un ADR).
- **TypeScript**: 7.x es la última, pero `openapi-typescript` exige 5.x y `typescript-eslint` admite menos de 6.1.
- **Aplicación en E2**: el alcance del catálogo usa enlaces y `fetch` nativos, React y
  declaraciones generadas con el PyYAML existente. Las bibliotecas de enrutamiento y
  consultas de la propuesta inicial se difieren. Visual Pipeline Studio sigue separado.

### D10. Entorno local
- **Decisión**: Docker Compose con `db`, `migrate` (misma imagen del backend, termina), `api` y `web`; puertos publicados solo en `127.0.0.1`. El descubrimiento se ejecuta con `docker compose run --rm api fdh discover`.
- **Razón**: un único backend desplegable y ningún servicio de pago.

### D11. Pruebas
- **Decisión**: pytest, pytest-asyncio y pytest-socket (solo equipo local); integración contra PostgreSQL real; contrato con datos sintéticos; Vitest y Testing Library en el portal. Cobertura informada, con mínimo del 85 % en dominio, descubrimiento y conectores.
- **Alternativas**: SQLite (prohibido por el principio VIII); Testcontainers (dependencia innecesaria con Compose).

### D12. Integración continua
- **Decisión**: flujos con permisos de solo lectura y acciones fijadas por SHA, en cada push y PR: estilo, tipos, pruebas sin red, migraciones, deriva de OpenAPI, portal, construcción de imágenes, prueba de humo con datos sintéticos, búsqueda de secretos con gitleaks y auditoría de dependencias informativa.
- **Razón**: controles proporcionales que no dependen de las API externas.

### D13. Observabilidad
- **Decisión**: logs JSON con la biblioteca estándar e identificador de ejecución; historial en base de datos; `/health`.
- **Alternativas**: métricas y trazas con herramientas especializadas (FDH-008).

### D14. Trabajo en paralelo sin ramas nuevas
- **Decisión**: `git worktree add --detach` por línea de trabajo y una sola persona o sesión integradora que aplica los commits con `cherry-pick` en la rama de desarrollo.
- **Razón**: aísla el trabajo (principio IX) sin crear ramas.
- **Alternativas**: escritura simultánea en la misma carpeta (causó un incidente); ramas por tarea (no autorizadas).

### D15. Compatibilidad comprobada
- **Fecha**: 2026-11-26 (UTC), en un proyecto temporal fuera del repositorio.
- **Comprobado**: las dependencias de D02, D03 y D11 resuelven e importan en Python 3.13.18. Contra `postgres:18` (18.7, `postgres@sha256:c699303802144847d238196173655dbbecf7a96aeca1565f2b02eb671a1f0b6b`), SQLAlchemy 2.1.9 con asyncpg 0.32.0 crea la extensión `unaccent`, usa bloqueos consultivos y rechaza escrituras en transacciones de solo lectura. La imagen declara el volumen `/var/lib/postgresql` y guarda datos en `18/docker`.
- **Licencias**: MIT, BSD, Apache-2.0 y PSF, salvo `certifi` (MPL-2.0, ejecución) y `pathspec` (MPL-2.0, solo desarrollo), usadas sin modificar. FastAPI 0.165 incorpora `opentelemetry-api` (Apache-2.0).
- **Portal**: Vitest 5 no declara soporte para Node 23; las pruebas y la compilación usan Node 24.
- **Decisión**: no se cambia ninguna versión.

### D16. Validación de contratos y controles de la cadena de suministro
- **Decisión**: `openapi-spec-validator` y PyYAML como dependencias de desarrollo; gitleaks, `pip-audit` y `npm audit` solo en la integración continua.
- **Razón**: validar formalmente el contrato OpenAPI y compararlo con la API en las pruebas; detectar secretos y dependencias vulnerables. Licencias Apache-2.0 y MIT en las dependencias de Python.
- **Alternativas**: comprobar solo la sintaxis (no detecta un documento inválido).

### D17. Intervalo entre solicitudes y token opcional (E2)
- **Decisión**: intervalo mínimo de 1 s entre inicios de solicitudes por fuente; token opcional leído de la variable que nombre la fuente y enviado en la cabecera que declare el adaptador.
- **Razón**: el intervalo coincide con el `Crawl-delay: 1` publicado en `www.datos.gov.co` para su sitio web (no documentado para la API); la referencia oficial recomienda el token y sin él la cuota es compartida por dirección IP.
- **Alternativas**: sin pausa (E1); token obligatorio (la lectura pública no lo exige); limitador entre procesos (innecesario para un comando local con un bloqueo por fuente).

### D18. Comprobación en navegador (E2)
- **Decisión**: un script de Node que controla Chrome sin interfaz mediante su protocolo de depuración, sin dependencias.
- **Razón**: comprueba el portal real servido por nginx, con su CSP, sin instalar navegadores ni paquetes adicionales.
- **Alternativas**: Playwright (descarga navegadores; sin espacio suficiente y sin necesidad para este alcance).

