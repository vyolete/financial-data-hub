# World Bank — Data360, Data Catalog API e Indicators API

**Estado**: Data360 accesible y elegida para FDH-001 el 2026-11-25 ([ADR-0008](../../../../docs/adr/0008-world-bank-data360.md)); Data Catalog API no utilizable en las pruebas; Indicators API accesible, candidata para extracción en FDH-002 y FDH-003. Requisitos: FDH-001-FR-06, NFR-01, NFR-02.

## Objetivo
Determinar qué API puede alimentar el segundo adaptador de descubrimiento y bajo qué condiciones.

## Método y reproducción
Solicitudes GET sin autenticación ni credenciales, pausa de 1,1 s, tiempo de espera de 10 s por operación. Ejecutadas el 2026-11-26 (UTC) con Python 3.9.6 y el repositorio en `10e5279`. Los scripts se confirmaron después; cada evidencia registra su SHA-256.

```bash
python3 -I research/experiments/discovery-probe/probe.py world-bank
python3 -I research/experiments/discovery-probe/followup.py   # incluye también Socrata
```

| Evidencia | Solicitudes |
|---|---|
| [probe](evidence/probe-2026-11-26T004520Z.json) | 29: 14 a Indicators y 15 al Data Catalog |
| [seguimiento del límite](evidence/followup-2026-11-26T004654Z.json) | 4 al Data Catalog |

## Data360 API (`https://data360api.worldbank.org/data360`)

### Método y evidencia
Segunda ronda, 2026-11-26 (UTC), con Python 3.9.6 y el repositorio en `2d4ee6b`. Los scripts se confirmaron después; cada evidencia registra su SHA-256. Sin credenciales.

```bash
python3 -I research/experiments/discovery-probe/round2.py data360
python3 -I research/experiments/discovery-probe/round2_datasets.py
```

| Evidencia | Solicitudes |
|---|---|
| [segunda ronda](evidence/round2-2026-11-26T010020Z.json) | 26: 1 a la especificación, 22 a Data360 y 3 al Data Catalog |
| [datasets](evidence/round2-datasets-2026-11-26T010325Z.json) | 7 a Data360 |

En la primera evidencia **no son válidos** los campos `checks` sobre solapamiento y unicidad, `unique_ids` ni la solicitud T18: leyeron `series_description.idno`, ausente en los datasets. La segunda evidencia usa `idno` y corrige la paginación. Los conteos por campo de la primera sí son válidos.

### Documentación oficial
- [Especificación OpenAPI](https://github.com/worldbank/open-api-specs/blob/main/Data360%20Open_API.json) (v1, OpenAPI 3.0.1), que alimenta la [página de la API](https://data360.worldbank.org/en/api). Su [README](https://github.com/worldbank/open-api-specs) indica que no requiere autenticación. La especificación declara CC BY 4.0 en `info.license`.
- El portal se anuncia como beta.

### Hechos observados
- `POST /searchv2` con cuerpo JSON: `search`, `filter`, `top`, `skip`, `count`, `facets`. Respuesta: `@odata.count` y `value[]`.
- `search="*"`: 12601 entradas; 9859 `indicator`, 174 `dataset` y otros tipos. El filtro `type eq 'dataset'` devolvió solo datasets.
- Paginación: 174 datasets en dos páginas, 174 distintos. `finance`: 42 en tres páginas, 42 distintos y mismo orden al repetir la primera.
- Más allá del total: 200 vacío. `skip` mayor de 100000: 400.
- Un dataset se recupera con `filter="type eq 'dataset' and idno eq '<id>'"` (conteo 1). `POST /metadata` **no quedó verificado**: la única solicitud (T18) envió el identificador `None` por el error de campo descrito arriba.
- Errores: `top` negativo o textual, filtro desconocido, propiedad desconocida y JSON mal formado devuelven **400** con mensaje.
- Tiempos con páginas de 100 datasets (unos 1,2 MB, 5 muestras): 1077–2971 ms, mediana 1213 ms.
- No se observó 429 en 29 solicitudes; no se intentó provocarlo.

### Metadatos (174 datasets)

| Campo | Ruta | Con valor |
|---|---|---|
| Identificador | `idno` | 174 |
| Título | `series_description.name` | 174 |
| Descripción | `series_description.definition_long` | 169 |
| Última actualización | `series_description.date_last_update` | 174 |
| Licencia (lista con `name`, `uri`, `note`) | `series_description.license[]` | 153 |
| Requisito de cita | `series_description.citation_requirement` | 118 |
| Temas | `series_description.topics[]` | 131 |
| Fuentes | `series_description.sources[]` | 153 |
| Etiquetas | `tags[].tag` | 40 |
| Enlaces | `series_description.links[]`, `api_link`, `csv_link`, `json_link`, `api_explorer_link` | 174 |
| Entidad autora | `series_description.authoring_entity` | 0 |

- `data_confidentiality_name`: `Public` en 173; uno sin valor.
- **Licencias heterogéneas**: ver la revisión siguiente.

### Revisión de licencias
2026-11-26 (UTC), repositorio en `d7cb98e`: `python3 -I research/experiments/discovery-probe/data360_licenses.py`. [Evidencia](evidence/licences-2026-11-26T011922Z.json), 2 solicitudes, 174 datasets distintos. Corrige una cifra anterior: **61 eran entradas de licencia externa, no datasets**; son 59 datasets.

| Grupo (excluyente) | Datasets | Con enlace | Con nota | Con requisito de cita |
|---|---|---|---|---|
| CC BY 4.0 o sin versión | 69 | 67 | 59 | 45 |
| Licencia especificada externamente | 59 | 36 | 56 | 48 |
| Sin licencia declarada | 21 | 0 | 0 | 3 |
| Otras con nombre (CC BY 3.0 IGO, SA, GPL, propias, etc.) | 16 | 14 | 13 | 15 |
| No comercial o sin derivados | 9 | 9 | 9 | 7 |

- 152 datasets declaran una licencia, uno declara tres y 21 ninguna.
- 23 de los 59 externos no tienen enlace a la licencia. Los enlaces existentes apuntan sobre todo a terceros; el más frecuente es `www.imf.org` (13).
- La agrupación usa solo los nombres declarados. **No se leyeron los textos enlazados ni las notas**, y no determina qué está permitido.
- Consecuencia: extracción y redistribución quedan `undetermined` en cada dataset. Los 21 sin licencia y los 59 externos requieren revisión humana antes de usar sus datos.

## Data Catalog API (`https://datacatalogapi.worldbank.org/ddhxext`)

### Hechos observados
- Las 22 solicitudes de las dos rondas respondieron **429** `Rate limit is exceeded`, con `Retry-After` entre 30 y 47 s, incluida la primera.
- En el seguimiento, una búsqueda se intentó 4 veces esperando lo indicado por `Retry-After`, y en la segunda ronda otras 3; todas respondieron 429.
- En la primera ejecución el script siguió enviando otras solicitudes mientras recibía 429, sin esperar. Esas 15 respuestas no permiten evaluar cada endpoint.
- No se obtuvo ningún dato: estructura, paginación, metadatos y errores quedan **sin verificar**.

### Documentación
- El [artículo oficial](https://datahelpdesk.worldbank.org/knowledgebase/articles/1886698-data-catalog-api) indica que la API sigue en revisión y remite a [documentación provisional en un gist](https://gist.github.com/tgherzog/e6090f9b2ba74f49f75b228f5c7169b9).
- El gist describe `DatasetList`, `Search` y `DatasetView` con `$top` y `$skip`. No menciona autenticación ni límites.

### Interpretación
La causa es desconocida (cuota anónima compartida, bloqueo por origen o necesidad de clave son **hipótesis**). Las pruebas cubren dos ventanas cortas desde un solo equipo: no demuestran que la API sea inviable en general, pero hoy no permiten construir sobre ella.

## Indicators API (`https://api.worldbank.org/v2`)

### Hechos observados
- Respuestas 200 sin autenticación. El formato predeterminado es XML; `format=json` devuelve JSON.
- Forma: `[metadatos, elementos]`, con `page`, `pages`, `per_page` y `total`. Los tipos de `page` y `per_page` varían entre texto y número.
- 29544 indicadores y 71 fuentes. La fuente 2 declara 1498 indicadores.
- Paginación por `page` y `per_page`; las páginas 1 y 2 no se solaparon. Una página posterior a la última devuelve 200 vacío.
- **Los errores llegan como 200**: indicador inexistente, `per_page=abc` y `per_page=0` devuelven `[{"message": [...]}]` con id 120.
- `q=gdp` no filtró: el total siguió en 29544. No se halló búsqueda por texto en la documentación consultada.
- Tiempos con 100 indicadores (4 muestras): 240–849 ms.

### Metadatos

| Entidad | Con valor | Ausente |
|---|---|---|
| Indicador (muestra de 100) | `id`, `name`, `source`: 100; `sourceNote` y `sourceOrganization`: 41; `topics`: 37 | licencia, fechas, URL, publicador explícito |
| Fuente (71) | `id`, `code`, `name`, `lastupdated`: 71; `metadataavailability`: 66 | `description` y `url`: 0 |

### Documentación
[Acerca de la API](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation): versión 2, sin claves. [Estructura de llamadas](https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures): `per_page` predeterminado 50.

### Unicidad de identificadores en Indicators API
[identity](evidence/identity-2026-11-26T010521Z.json) (176 solicitudes, script `research/experiments/discovery-probe/worldbank_identity.py`) estudia la unicidad de identificadores entre fuentes. La produjo otra sesión de trabajo. Se revisaron el código, los hashes de los scripts y la coherencia interna de las cifras; **no se reprodujo**.

- 71 fuentes; el listado global devolvió 29544 filas con 29490 códigos distintos.
- 3581 códigos aparecen en más de una fuente (hasta en 14), sin diferencias de nombre.
- Las fuentes 67 y 90 entregaron menos filas que el total declarado (104 de 114 y 47 de 48).
- En una muestra de 95 indicadores, 75 devolvieron metadatos; 49 declaran `CC BY-4.0` y 26 no declaran licencia.
- Consecuencia para FDH-002 y FDH-003: el código de indicador no basta como identidad; hay que combinarlo con la fuente.
- La ejecución usó un tiempo de espera de 60 s y hasta 260 solicitudes, límites propios de investigación y no del producto. Su campo `repository_commit` registra el identificador que tenía ese commit antes de corregir su autoría; el contenido es el mismo que el de `6bfd09b`.

## Condiciones de uso
Consultadas el 2026-11-26 (UTC).

| Documento | Contenido |
|---|---|
| [Términos para datasets](https://www.worldbank.org/ext/en/legal/terms-conditions/datasets) (23-03-2018) | CC BY 4.0 salvo indicación; atribución; cierto material de terceros no puede redistribuirse sin consentimiento; permite usar las API para acceder a los datasets |
| [Licencias del catálogo](https://datacatalog.worldbank.org/public-licenses) | CC BY 4.0 predeterminada para datos abiertos del Banco; otros datasets tienen otras licencias |
| [Términos del sitio](https://www.worldbank.org/ext/en/legal/terms-conditions) (25-07-2025) | Volumen razonable de solicitudes; remite a los términos específicos para datasets; para otros materiales, la API solo admite ciertos usos no comerciales |

**Declaración**: el 2026-11-25 la mantenedora declaró en sesión de trabajo `allowed` la publicación de metadatos de Data360, con atribución y licencia declarada de cada dataset (ver [inventario](../../inventory.md)). Consta en la especificación aprobada ([registro de aprobación](https://github.com/vyolete/financial-data-hub/issues/2#issuecomment-7179859703)). La declaración no cambia el estado de revisión de los datasets ni autoriza redistribuir sus datos.

## Decisión
El 2026-11-25 se eligió Data360 para FDH-001, con una entrada `dataset` por dataset del catálogo. Indicators API queda como candidata para extraer indicadores y series económicas en FDH-002 y FDH-003. El Data Catalog queda como investigación. Ver [ADR-0008](../../../../docs/adr/0008-world-bank-data360.md).

## Pendiente
- Elegir los campos para URL oficial, publicador y categoría.
- Revisar los términos aplicables a datasets con licencia externa o ausente.
- Seguir el estado beta y los cambios de la especificación.
