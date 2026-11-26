# Dependencias y licencias

Generado el 2026-11-26 (UTC) a partir de `backend/uv.lock`, de los metadatos instalados y de `frontend/package-lock.json`. Compatibilidad evaluada respecto de Apache-2.0 ([ADR-0004](../docs/adr/0004-apache-2-license.md)); no sustituye una revisión legal.

Las licencias MIT, BSD, Apache-2.0, ISC, 0BSD, PSF y BlueOak-1.0.0 son permisivas. MPL-2.0 es copyleft por archivo: estas dependencias se usan sin modificar. En ejecución solo `certifi` es MPL-2.0; `pathspec` y `lightningcss` se usan solo para desarrollar o compilar.

## Backend

| Paquete | Versión | Uso | Licencia |
|---|---|---|---|
| alembic | 1.20.1 | directa | MIT |
| annotated-doc | 0.0.7 | transitiva | MIT |
| annotated-types | 0.8.0 | transitiva | MIT |
| anyio | 4.16.0 | transitiva | MIT |
| ast-serialize | 0.13.1 | transitiva | MIT |
| asyncpg | 0.32.0 | directa | Apache-2.0 |
| attrs | 26.1.0 | transitiva | MIT |
| certifi | 2026.11.20 | transitiva | Mozilla Public License 2.0 (MPL 2.0) |
| click | 8.5.1 | transitiva | BSD-3-Clause |
| colorama | 0.4.6 | transitiva | sin verificar: solo se instala en Windows |
| coverage | 7.17.5 | transitiva | Apache-2.0 |
| fastapi | 0.165.0 | directa | MIT |
| greenlet | 3.5.6 | transitiva | MIT AND PSF-2.0 |
| h11 | 0.16.0 | transitiva | MIT License |
| httpcore | 1.0.9 | transitiva | BSD-3-Clause |
| httpx | 0.28.1 | directa | BSD License |
| idna | 3.20 | transitiva | BSD-3-Clause |
| iniconfig | 2.3.1 | transitiva | MIT |
| jsonschema | 4.26.0 | transitiva | MIT |
| jsonschema-path | 0.5.0 | transitiva | Apache Software License |
| jsonschema-specifications | 2025.9.1 | transitiva | MIT |
| lazy-object-proxy | 1.13.0 | transitiva | BSD-2-Clause |
| librt | 0.17.0 | transitiva | MIT |
| mako | 1.4.3 | transitiva | MIT |
| markupsafe | 3.0.4 | transitiva | BSD-3-Clause |
| mypy | 2.4.1 | desarrollo | MIT |
| mypy-extensions | 1.2.0 | transitiva | MIT |
| openapi-schema-validator | 0.9.0 | transitiva | BSD License |
| openapi-spec-validator | 0.9.0 | desarrollo | Apache-2.0 |
| opentelemetry-api | 1.45.2 | transitiva | Apache-2.0 |
| packaging | 26.4 | transitiva | Apache-2.0 OR BSD-2-Clause |
| pathable | 0.6.0 | transitiva | Apache Software License |
| pathspec | 1.1.1 | transitiva | Mozilla Public License 2.0 (MPL 2.0) |
| pluggy | 1.7.0 | transitiva | MIT License |
| pydantic | 2.14.4 | directa | MIT |
| pydantic-core | 2.50.5 | transitiva | MIT |
| pydantic-settings | 2.16.3 | directa | MIT |
| pygments | 2.21.0 | transitiva | BSD-2-Clause |
| pytest | 9.2.0 | desarrollo | MIT |
| pytest-asyncio | 1.5.0 | desarrollo | Apache-2.0 |
| pytest-cov | 7.1.0 | desarrollo | MIT |
| pytest-socket | 0.8.1 | desarrollo | MIT |
| python-dotenv | 1.2.4 | transitiva | BSD-3-Clause |
| pyyaml | 6.0.4 | desarrollo | MIT License |
| referencing | 0.37.0 | transitiva | MIT |
| rfc3339-validator | 0.1.4 | transitiva | MIT License |
| rpds-py | 2026.9.1 | transitiva | MIT |
| ruff | 0.17.6 | desarrollo | MIT |
| six | 1.17.0 | transitiva | MIT License |
| sqlalchemy | 2.1.9 | directa | MIT |
| starlette | 1.10.0 | transitiva | BSD-3-Clause |
| typing-extensions | 4.16.0 | transitiva | PSF-2.0 |
| typing-inspection | 0.4.5 | transitiva | MIT |
| uvicorn | 0.54.0 | directa | BSD-3-Clause |

## Portal: dependencias declaradas

| Paquete | Versión | Uso | Licencia |
|---|---|---|---|
| react | 19.3.1 | directa | MIT |
| react-dom | 19.3.1 | directa | MIT |
| @eslint/js | 10.0.1 | desarrollo | MIT |
| @testing-library/dom | 10.4.2 | desarrollo | MIT |
| @testing-library/react | 16.3.3 | desarrollo | MIT |
| @types/react | 19.3.3 | desarrollo | MIT |
| @types/react-dom | 19.3.0 | desarrollo | MIT |
| @vitejs/plugin-react | 6.3.0 | desarrollo | MIT |
| eslint | 10.15.0 | desarrollo | MIT |
| jsdom | 31.0.1 | desarrollo | MIT |
| typescript | 5.9.3 | desarrollo | Apache-2.0 |
| typescript-eslint | 8.74.0 | desarrollo | MIT |
| vite | 8.3.8 | desarrollo | MIT |
| vitest | 5.1.2 | desarrollo | MIT |

Árbol completo del portal por licencia: 0BSD (1), Apache-2.0 (17), BSD-2-Clause (8), BSD-3-Clause (3), BlueOak-1.0.0 (3), ISC (7), MIT (158), MPL-2.0 (12).
