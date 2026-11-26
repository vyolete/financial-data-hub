# Socrata Discovery API — www.datos.gov.co

**Estado**: probada en vivo; publicación de metadatos declarada `allowed` (recogida en la especificación aprobada); referencia oficial de la API sin leer. Requisitos: FDH-001-FR-01, FR-02, NFR-01, NFR-02.

## Objetivo
Comprobar acceso, estructura, paginación, metadatos, errores, tiempos y condiciones de uso antes de implementar el adaptador.

## Método y reproducción
Solicitudes GET sin autenticación, una pausa de 1,1 s entre ellas, tiempo de espera de 10 s por operación de red y sin reintentos. Ejecutadas el 2026-11-26 (UTC) con Python 3.9.6 y el repositorio en `10e5279`. Los scripts se confirmaron después; cada evidencia registra su SHA-256.

```bash
python3 -I research/experiments/discovery-probe/probe.py socrata
python3 -I research/experiments/discovery-probe/followup.py   # incluye también World Bank
```

| Evidencia | Solicitudes |
|---|---|
| [probe](evidence/probe-2026-11-26T004408Z.json) | 27 |
| [seguimiento de paginación](evidence/followup-2026-11-26T004632Z.json) | 6 |

La evidencia guarda estado, tiempo, tamaño, hash del cuerpo, esquema y conteos. No guarda títulos, descripciones, nombres ni identificadores. Los hashes no permiten reconstruir las respuestas; al repetir las pruebas los conteos pueden variar porque el catálogo cambia.

## Hechos observados

### Acceso y estructura
- `https://api.us.socrata.com/api/catalog/v1?domains=www.datos.gov.co&only=datasets` y `https://www.datos.gov.co/api/catalog/v1` respondieron 200 con el mismo tamaño y `resultSetSize` (S01, S02). Añadir `search_context` no cambió esos valores (S03).
- Respuesta JSON: `results[]`, `resultSetSize`, `timings`, `warnings`. Cada resultado contiene `resource`, `classification`, `metadata`, `permalink`, `link`, `owner` y `creator`.
- Sin filtros de texto: 8475 datasets. Con `q=presupuesto`: 145 datasets y 563 resultados sin `only=datasets` (80 de los primeros 100 eran datasets; el resto `federated_href`, `filter`, `href` y `chart`).
- `q=inversión` y `q=inversion` devolvieron el mismo total (100) con distinto primer resultado.

### Paginación
- `limit` y `offset` funcionan; 100 por página devolvió 100 y 45 registros para un total de 145.
- Más allá del total: 200 con `results` vacío.
- `offset + limit > 10000`: 400, con un mensaje que remite a la paginación profunda (S12). No se probó la paginación profunda.
- **Inestabilidad**: en la primera ejecución las páginas 0 y 100 compartieron 1 identificador, por lo que 145 resultados entregaron 144 distintos. En el seguimiento no hubo solapamiento con orden predeterminado, `createdAt` ni `name`. Con una sola observación no se conoce la causa ni la frecuencia.

### Errores

| Caso | Respuesta |
|---|---|
| `offset + limit > 10000` | 400 con mensaje |
| Dominio inexistente | 404 `Domain not found` |
| `limit=-1` o `limit=abc` | 500 genérico |
| `only` con valor inválido | 200 sin resultados |
| `limit=10001` en una consulta sin resultados | 200 sin resultados; no demuestra que exista o no un máximo |

Consecuencias: un error del cliente puede llegar como 500 (y se reintentaría), y una configuración errónea puede parecer una búsqueda vacía. No se observó 429 ni cabeceras de límite; no se intentó provocarlos.

### Tiempos

| Solicitud | Muestras | Mínimo | Mediana | Máximo |
|---|---|---|---|---|
| 1 registro | 6 | 488 ms | 562 ms | 1920 ms |
| 100 registros (unos 0,5–0,9 MB) | 12 | 938 ms | 1142 ms | 11740 ms |

Una de las 12 solicitudes de 100 registros superó 10 s y otra tardó 9,2 s. El tiempo de espera del script aplica a cada operación de red, no al total, por eso la primera no se canceló. La muestra es pequeña y de un solo equipo y momento.

### Metadatos (145 resultados de `q=presupuesto` en la primera ejecución, 144 distintos)

| Campo | Ruta | Con valor |
|---|---|---|
| Identificador | `resource.id` | 145 |
| Título | `resource.name` | 145 |
| Descripción | `resource.description` | 145 |
| Publicador (candidato) | `resource.attribution` | 145 (86 de 100 sin `only`) |
| Fechas | `resource.createdAt`, `updatedAt`, `data_updated_at`, `metadata_updated_at`, `publication_date` | 145 |
| Categoría | `classification.domain_category` | 136 |
| Etiquetas | `classification.domain_tags` | 125 |
| Licencia declarada | `metadata.license` | 145 |
| URL | `permalink`, `link` | 145 |

- `classification.categories` y `classification.tags` llegaron vacíos.
- Licencias declaradas: CC BY-SA 4.0 en 142; CC BY 4.0, CC BY-ND 4.0 y CC0 en 1 cada una.
- Las categorías tienen variantes de mayúsculas («Participación Ciudadana» y «Participación ciudadana»).
- La respuesta incluye `owner.display_name`, `creator.display_name` y el campo `contact_email` (nulo en el esquema observado). Son datos personales o potencialmente personales: el adaptador no debe conservarlos.
- `/api/views/{id}.json`, probado con un dataset, expone `licenseId` y `license.termsLink`.

## Segunda ronda: cursor y tamaño de página
2026-11-26 (UTC), repositorio en `2d4ee6b`: `python3 -I research/experiments/discovery-probe/round2.py socrata`. [Evidencia](evidence/round2-2026-11-26T010240Z.json), 6 solicitudes.

- `scroll_id` vacío y luego con el último identificador de cada página recorrió 145 resultados en páginas de 100, 45 y 0, con 145 distintos.
- La primera página con cursor no contiene los mismos identificadores que la primera con `offset`: el orden difiere.
- `scroll_id` junto con `order`: 400 `cannot both be specified`, tras 7,8 s.
- `limit=150` devolvió los 145 resultados: 100 no es el máximo de la plataforma.
- Todas las solicitudes con `limit=100` de ambas rondas (16): mediana 1142 ms, máximo 11740 ms, una por encima de 10 s.

## Documentación y condiciones de uso
Consultadas el 2026-11-26 (UTC).

| Fuente oficial | Contenido |
|---|---|
| [Términos del portal](https://herramientas.datos.gov.co/terminos) | Los datos e información publicados son públicos; permite redistribución, compilación, extracción, copia, difusión, modificación y adaptación; exige citar «Fuente: Portal de Datos Abiertos www.datos.gov.co» y la última actualización cuando exista; prohíbe alterar o suprimir los metadatos de actualización y condiciones de uso. La página no indica fecha de versión ni menciona la API |
| [Application Tokens](https://dev.socrata.com/docs/app-tokens.html) | Sin token se aplica un límite mucho menor; el exceso responde 429 |
| [robots.txt](https://www.datos.gov.co/robots.txt) | `Crawl-delay: 1`; `/api/catalog` no figura excluido |
| [Referencia de Discovery API](https://socratadiscovery.docs.apiary.io/) | La página no pudo leerse de forma automática: **los parámetros descritos aquí provienen de las pruebas, no de su documentación** |

## Interpretación y pendientes (no son hechos verificados)
- **Hipótesis**: los términos permitirían publicar metadatos con la cita exigida. Cada dataset conserva su licencia, incluida alguna sin derivados.
- **Declaración**: el 2026-11-25 la mantenedora declaró en sesión de trabajo `allowed` la publicación de metadatos, con la cita exigida y la licencia declarada (ver [inventario](../../inventory.md)). Consta en la especificación aprobada ([registro de aprobación](https://github.com/vyolete/financial-data-hub/issues/2#issuecomment-7179859703)).
- **Pendiente**: leer la referencia oficial de la API.
- **Pendiente**: la causa del resultado anterior con cero datasets (LAB-01) no se pudo determinar. Estas pruebas sí obtuvieron resultados.
- **Sin probar**: token de aplicación, 429 y `Retry-After`, otros dominios, recorridos de más de 10000 resultados.
