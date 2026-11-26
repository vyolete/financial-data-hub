# World Bank — Data Catalog API e Indicators API

**Estado**: Data Catalog API no utilizable en las pruebas; Indicators API accesible. Se requiere aprobación antes de elegir. Requisitos: FDH-001-FR-06, NFR-01, NFR-02.

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

## Data Catalog API (`https://datacatalogapi.worldbank.org/ddhxext`)

### Hechos observados
- Las 19 solicitudes respondieron **429** `Rate limit is exceeded`, con `Retry-After` entre 30 y 43 s, incluida la primera.
- En el seguimiento, una búsqueda se intentó 4 veces esperando lo indicado por `Retry-After`; las 4 respondieron 429.
- En la primera ejecución el script siguió enviando otras solicitudes mientras recibía 429, sin esperar. Esas 15 respuestas no permiten evaluar cada endpoint.
- No se obtuvo ningún dato: estructura, paginación, metadatos y errores quedan **sin verificar**.

### Documentación
- El [artículo oficial](https://datahelpdesk.worldbank.org/knowledgebase/articles/1886698-data-catalog-api) indica que la API sigue en revisión y remite a [documentación provisional en un gist](https://gist.github.com/tgherzog/e6090f9b2ba74f49f75b228f5c7169b9).
- El gist describe `DatasetList`, `Search` y `DatasetView` con `$top` y `$skip`. No menciona autenticación ni límites.

### Interpretación
La causa es desconocida (cuota anónima compartida, bloqueo por origen o necesidad de clave son **hipótesis**). Las pruebas cubren unos minutos desde un solo equipo: no demuestran que la API sea inviable en general, pero hoy no permiten construir sobre ella.

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

## Condiciones de uso
Consultadas el 2026-11-26 (UTC).

| Documento | Contenido |
|---|---|
| [Términos para datasets](https://www.worldbank.org/ext/en/legal/terms-conditions/datasets) (23-03-2018) | CC BY 4.0 salvo indicación; atribución; cierto material de terceros no puede redistribuirse sin consentimiento; permite usar las API para acceder a los datasets |
| [Licencias del catálogo](https://datacatalog.worldbank.org/public-licenses) | CC BY 4.0 predeterminada para datos abiertos del Banco; otros datasets tienen otras licencias |
| [Términos del sitio](https://www.worldbank.org/ext/en/legal/terms-conditions) (25-07-2025) | Volumen razonable de solicitudes; remite a los términos específicos para datasets; para otros materiales, la API solo admite ciertos usos no comerciales |

**Pendiente humano**: decidir si los metadatos de indicadores se rigen por los términos de datasets y declarar el permiso de publicación. Hasta entonces sigue `undetermined`.

## Decisión pendiente (requiere aprobación, FR-06)

| Opción | Ventaja | Coste |
|---|---|---|
| A. Indicators API, un indicador = un dataset | Accesible y paginada; descripción en parte de los registros | Un indicador es más fino que un dataset; sin búsqueda por texto; sin licencia ni fechas por registro |
| B. Indicators API, una fuente = un dataset | 71 entradas, más cercanas a una base de datos | Sin descripción ni URL en la respuesta |
| C. Volver a probar el Data Catalog (otro momento o con clave si existe una oficial) | Es el catálogo de datasets | Plazo y resultado inciertos |

Propuesta: A, limitando por fuente o tema en la configuración, y mantener C como investigación. No se sustituye nada sin aprobación.
