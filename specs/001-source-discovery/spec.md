# FDH-001 — Descubrimiento y catálogo de datos financieros

**Estado**: In Review (requiere aprobación de la persona mantenedora antes de implementar)
**Issue de seguimiento**: [#2](https://github.com/vyolete/financial-data-hub/issues/2)

## Clarifications

### Session 2026-11-25

- Q: ¿Qué fuentes Socrata y tipos de activo entran inicialmente? → A: `www.datos.gov.co`, solo datasets. Dominios, términos de búsqueda y límites son configurables. El núcleo del catálogo no se acopla a Socrata.
- Q: ¿Cómo se ejecuta el descubrimiento y hace falta autenticación? → A: Comando local bajo demanda. API y portal de solo lectura, sin autenticación exclusivamente para desarrollo local. Ningún servicio sin autenticación se expone públicamente.
- Q: ¿Cómo se identifica un dataset y qué ocurre al repetir el descubrimiento? → A: Se distinguen proveedor, plataforma tecnológica y dataset. La identidad es única y estable por fuente e identificador externo. Se actualizan los metadatos sin duplicar, se conservan procedencia e historial de búsquedas y no se eliminan automáticamente los datasets desaparecidos.
- Q: ¿Qué ocurre ante un fallo parcial? → A: Se conservan los registros válidos, se registran páginas procesadas y errores, la ejecución queda `partial` y puede repetirse sin duplicados.
- Q: ¿Qué límites iniciales se aplican? → A: Configurables: 100 registros por página, máximo 5 páginas por consulta, tiempo de espera de 10 segundos y máximo 3 reintentos con espera creciente, respetando `Retry-After`. No se reintentan indiscriminadamente errores permanentes. La API pagina de 20 en 20 por defecto, con un máximo de 100.
- Q: ¿Qué metadatos y filtros se requieren? → A: Identificador externo, título, descripción, proveedor, plataforma, publicador, categorías y temas originales, etiquetas, URL oficial, fechas disponibles, licencia, estado de verificación y procedencia. Filtros por texto, proveedor y categoría.
- Q: ¿Cómo se representan licencia y acceso? → A: Estados de revisión `pending`, `verified` y `restricted`. Condiciones de acceso y de redistribución por separado. La disponibilidad pública no implica permisos. Los metadatos pendientes se muestran cuando su publicación está permitida.
- Q: ¿Qué hacen la API y el portal con los metadatos de una fuente cuyo permiso de publicación no se ha determinado? → A: Ocultarlos. Cada fuente declara el permiso tras revisar sus condiciones; sin esa declaración no se muestran.
- Q: ¿Cuál es el papel de World Bank? → A: Segundo adaptador para demostrar la extensibilidad del catálogo, tras investigar su API oficial y condiciones de uso. Si no es viable, se registra evidencia y se solicita aprobación de una alternativa.
- Q: ¿Se completan los criterios de aceptación? → A: Sí, para todos los requisitos, incluidos procedencia, detalle, estados de interfaz, reintentos, logs, fechas de verificación, deduplicación y fallos parciales.
- Q: ¿Qué fuentes entran primero y cómo se relaciona FDH-001 con el motor de integración? → A: Socrata Colombia y World Bank. FDH-001 se limita a descubrimiento y catálogo; sus contratos se diseñan considerando la futura integración con el motor ETL.
- Q: ¿De qué API de World Bank se obtienen los datasets? → A: Data360, la API pública oficial, con una entrada de tipo dataset por dataset. El Data Catalog API queda como investigación porque respondió HTTP 429 en las pruebas.
- Q: ¿Qué permiso de publicación de metadatos tienen las fuentes iniciales? → A: `allowed` para `www.datos.gov.co` y World Bank Data360, mostrando atribución y la licencia declarada de cada dataset.
- Q: ¿Cómo se tratan el truncamiento y las esperas largas? → A: Alcanzar el máximo de páginas con resultados pendientes es un truncamiento intencional, distinto de un error: se marca `truncated`. Un `Retry-After` mayor de 60 segundos detiene los reintentos.
- Q: ¿Se muestran los datasets `restricted` de una fuente `allowed`? → A: No; en el MVP se ocultan en búsqueda y detalle.
- Q: ¿Qué APIs usa FDH-001 y qué ocurre con World Bank Indicators? → A: Socrata Colombia y World Bank Data360. Indicators API queda como candidata para extraer indicadores y series económicas en FDH-002 y FDH-003; su investigación se conserva.
- Q: ¿Cuándo una ejecución es `succeeded`, `partial` o `failed`? → A: `partial` si se recuperan registros válidos y hay fallos o rechazos; `failed` si todos los registros recuperados se rechazan por errores de validación; una búsqueda legítimamente vacía y sin errores es `succeeded`.
- Q: ¿Cómo se aplica el tiempo de espera? → A: Configurable, 10 segundos por intento, con un máximo de 3 reintentos adicionales y respeto de `Retry-After`.
- Q: ¿Cómo se representan categorías y temas? → A: Se admiten varios de cada uno.
- Q: ¿Cómo se administran los permisos? → A: Mediante configuración o comando local. Los permisos de metadatos se separan de los de extracción y redistribución de datos. No se asume que los datasets de Data360 compartan condiciones de uso.
- Q: ¿Qué se exige a los adaptadores? → A: Capacidades explícitas, independencia de la red y de la persistencia, localizadores de acceso extensibles y verificables e identidad estable por fuente e identificador externo.
- Q: ¿Entra la integración continua en FDH-001? → A: Sí, con pruebas y controles proporcionales al alcance.
- Q: ¿Anula el permiso de metadatos de una fuente las restricciones específicas de un dataset? → A: No; la restricción del dataset prevalece.
- Q: ¿Qué ocurre con un dataset que tiene un localizador inválido? → A: Permanece en el catálogo; el localizador no puede usarse para extracción hasta que se corrija.

## Escenarios de usuario

- Una persona analista busca datasets financieros por texto, filtra por proveedor y categoría, abre los metadatos y ve el estado de revisión, la licencia, las condiciones de acceso y redistribución y la procedencia.
- Una persona operadora ejecuta el descubrimiento mediante un comando local y ve resultados reales, o un fallo total o parcial explícito.

## Conceptos

| Concepto | Código | Definición |
|---|---|---|
| Fuente | `source` | Origen configurado de descubrimiento, con identificador estable (`source_id`). Declara proveedor, plataforma, ubicación y permiso de publicación de metadatos |
| Proveedor | `provider` | Organización responsable del catálogo de una fuente |
| Plataforma | `platform` | Tecnología del catálogo remoto; determina el adaptador (por ejemplo, Socrata) |
| Dataset | `dataset` | Entrada de una fuente, identificada por `source_id` e identificador externo (`external_id`) |
| Publicador | `publisher` | Entidad que, según la fuente, publica el dataset |
| Ejecución | `run` | Una invocación del descubrimiento sobre una fuente |
| Procedencia | `provenance` | Qué ejecuciones y búsquedas encontraron un dataset, desde qué URL y cuándo |
| Capacidad | `capability` | Función que un adaptador declara soportar, como la búsqueda por texto |
| Localizador | `access_locator` | Referencia de acceso declarada por la fuente |

Datasets de fuentes distintas son registros distintos, aunque compartan identificador externo.

## Fuentes iniciales

El estado de cada fuente se mantiene en el [inventario](../../research/sources/inventory.md).

La publicación de metadatos no concede extracción ni redistribución de datos, que permanecen `undetermined`.

| `source_id` | Proveedor | Plataforma | Publicación de metadatos | Atribución |
|---|---|---|---|---|
| `co-datos-gov` | MinTIC | Socrata | `allowed` (declarada el 2026-11-25) | «Fuente: Portal de Datos Abiertos www.datos.gov.co» y fecha de última actualización cuando exista |
| `int-worldbank-data360` | World Bank | Data360 | `allowed` (declarada el 2026-11-25) | The World Bank, nombre del dataset y fuente de los datos cuando se conozca |

## Requisitos

- **FDH-001-FR-01**: Descubrir datasets mediante la Socrata Discovery API, con un comando local bajo demanda, consultas configurables y paginación acotada. La fuente inicial es `www.datos.gov.co` y solo se incluyen datasets. Dominios, términos y límites son configurables.
- **FDH-001-FR-02**: Deduplicar por fuente e identificador externo, y conservar la procedencia y el historial de búsquedas. Repetir el descubrimiento actualiza los metadatos. Un dataset que deja de aparecer no se elimina automáticamente.
- **FDH-001-FR-03**: Persistir en PostgreSQL los metadatos y los registros de ejecución; repetir el descubrimiento no debe duplicar datasets.
  - Metadatos: identificador externo, título, descripción, proveedor, plataforma, publicador, categorías y temas originales (cero o varios de cada uno, textuales), etiquetas, URL oficial, fechas disponibles, licencias declaradas, estado de verificación y procedencia. Un valor ausente se registra como desconocido.
  - Se conservan los localizadores de acceso que declare la fuente, para la futura extracción. Cada uno registra tipo (lista extensible), URL, campo de origen y estado de verificación: `unverified` o, si su sintaxis no es una URL HTTPS válida, `invalid`. FDH-001 no los consulta ni descarga los datos que señalan. Un localizador `invalid` no elimina el dataset del catálogo, pero no puede usarse para extracción hasta que se corrija y supere de nuevo la validación.
  - Ejecución: identificador, fuente, parámetros, inicio y fin en UTC, estado, páginas procesadas, conteos (recibidos, creados, actualizados y rechazados), errores sanitizados y, por consulta, total declarado por la fuente (si lo hay) y marca `truncated`.
  - Estados: `running`; `succeeded` (sin fallos ni rechazos, aunque no haya resultados); `partial` (se recuperó al menos un registro válido y hubo fallos o rechazos); `failed` (hubo fallos o rechazos y no se recuperó ningún registro válido, incluido el caso de que todos se rechacen).
  - `truncated` indica que quedaron resultados tras alcanzar el máximo de páginas de una consulta. Es un límite intencional: no es un error ni cambia por sí solo el estado.
- **FDH-001-FR-04**: Exponer mediante FastAPI, en modo de solo lectura, búsqueda paginada, filtros por texto, proveedor y categoría (coincide con cualquiera de las categorías o temas originales), detalle de datasets y estado de las ejecuciones. Página predeterminada de 20 registros y máxima de 100.
- **FDH-001-FR-05**: Mostrar en un portal React de solo lectura los registros reales del catálogo y el estado de las ejecuciones; distinguir los estados vacío, cargando y fallido, y no presentar una ejecución `partial` o `failed` como exitosa.
- **FDH-001-FR-06**: Añadir World Bank como segundo adaptador de descubrimiento, tras verificar su API oficial y condiciones, sin modificar el núcleo del catálogo, que no depende de Socrata. Usa la API pública Data360, solo entradas de tipo dataset, con consultas configurables y los mismos límites. Cambiar de API requiere registrar evidencia y solicitar aprobación.
  - Todo adaptador declara explícitamente sus capacidades; una configuración que exija una no soportada se rechaza antes de la primera solicitud.
  - Los adaptadores no acceden a la red ni a la persistencia: de ambas se ocupa el núcleo.
- **FDH-001-NFR-01**: Solicitudes acotadas, tiempo de espera, política de reintentos, logs sanitizados y ningún secreto en Git.
  - Tiempo máximo configurable por intento, 10 segundos por defecto, y máximo 3 reintentos adicionales (4 intentos en total), con espera creciente y respeto de `Retry-After`. Si `Retry-After` supera 60 segundos, no se reintenta y la ejecución termina `partial` o `failed` según las reglas de estado.
  - Se reintentan fallos de conexión, tiempos de espera y respuestas HTTP 429, 500, 502, 503 y 504; los demás errores no se reintentan.
  - API, portal y base de datos sin autenticación solo son accesibles desde el equipo local.
- **FDH-001-NFR-02**: Registrar URL oficial de la fuente, fecha de verificación y estado de acceso y redistribución; las condiciones desconocidas siguen siendo desconocidas.
  - Estado de revisión: `pending` (predeterminado), `verified` o `restricted`. Cambiarlo requiere una revisión humana con evidencia y fecha.
  - Las condiciones de acceso y de redistribución se registran por separado. La disponibilidad pública no implica permisos.
  - Cada fuente tiene un permiso de publicación de metadatos: `allowed`, `denied` o `undetermined` (predeterminado). La API y el portal solo muestran metadatos de fuentes `allowed`, y nunca los de datasets `restricted`.
  - El permiso de la fuente no anula una restricción específica de un dataset: una persona la registra como `restricted`, con evidencia y fecha, y prevalece.
  - Cada dataset tiene, por separado, un permiso de extracción y otro de redistribución de datos, con los mismos valores y `undetermined` por defecto. No se heredan del permiso de metadatos ni de una licencia declarada.
  - Permisos y estados de revisión se administran mediante configuración o comando local, con evidencia y fecha de una persona. La API y el portal no los modifican.
  - Las licencias se conservan textualmente, con su enlace y requisito de cita si se declaran. Pueden ser varias, externas o estar ausentes.
  - La API y el portal muestran la atribución exigida por la fuente y las licencias declaradas del dataset.
- **FDH-001-NFR-03**: Pruebas y evidencias reproducibles; sin resultados inventados. Las pruebas automatizadas no dependen de la red y usan datos sintéticos identificados; las pruebas en vivo se ejecutan y documentan por separado. Desde FDH-001, la integración continua en GitHub Actions ejecuta las pruebas sin red y controles proporcionales al alcance.

## Límites configurables

| Límite | Valor inicial |
|---|---|
| Registros por página solicitada a la fuente | 100 |
| Páginas por consulta | 5 |
| Tiempo máximo por intento (configurable) | 10 s |
| `Retry-After` máximo aceptado | 60 s |
| Reintentos adicionales por solicitud | 3 |
| Tamaño de página de la API, predeterminado | 20 |
| Tamaño de página de la API, máximo | 100 |

## Criterios de aceptación

Salvo indicación contraria, las fuentes de los criterios tienen publicación de metadatos `allowed`.

| ID | Requisitos | Criterio |
|---|---|---|
| FDH-001-AC-01 | FR-01 | Dada la configuración inicial, cuando se ejecuta el comando, entonces solo solicita datasets de `www.datos.gov.co`, con un máximo de 100 registros por página y 5 páginas por consulta, y se detiene antes si no hay más resultados |
| FDH-001-AC-02 | FR-01 | Al cambiar en la configuración un dominio, término o límite, las solicitudes cambian sin modificar código |
| FDH-001-AC-03 | FR-02 | Dado un dataset encontrado por dos consultas de la misma fuente, existe un solo registro y su historial identifica ambas |
| FDH-001-AC-04 | FR-02, FR-03 | Al repetir una ejecución, el número de datasets no aumenta con las mismas respuestas, los metadatos modificados se actualizan, se conserva la primera observación y la nueva ejecución queda en el historial |
| FDH-001-AC-05 | FR-02 | Un dataset ausente en una ejecución posterior se conserva con la fecha de su última observación |
| FDH-001-AC-06 | FR-02 | El mismo identificador externo en dos fuentes produce dos registros |
| FDH-001-AC-07 | FR-03 | Cada dataset persistido conserva los metadatos requeridos, incluidas todas sus categorías, temas y licencias, y su procedencia; los valores ausentes figuran como desconocidos y no se descargan datos |
| FDH-001-AC-08 | FR-03 | Si se recuperan registros válidos y alguna solicitud falla, los válidos permanecen, la ejecución queda `partial` con páginas procesadas y errores, y repetirla no crea duplicados |
| FDH-001-AC-09 | FR-03 | Si hay fallos y no se recupera ningún registro válido, la ejecución queda `failed`, los datos anteriores no cambian y ni la API ni el portal indican éxito |
| FDH-001-AC-10 | FR-03 | Una búsqueda sin resultados y sin errores queda `succeeded` con cero registros |
| FDH-001-AC-11 | FR-03 | Con registros válidos e inválidos, los inválidos se cuentan como rechazados y se informan, los válidos se guardan y la ejecución queda `partial` |
| FDH-001-AC-12 | FR-04 | Sin indicar tamaño, la API devuelve como máximo 20 registros; permite solicitar hasta 100 y nunca devuelve más de 100 |
| FDH-001-AC-13 | FR-04 | Los filtros por texto, proveedor y categoría funcionan por separado y combinados; un dataset con varias categorías o temas coincide con cualquiera de ellos, y sin coincidencias se devuelve una colección vacía |
| FDH-001-AC-14 | FR-04 | El detalle devuelve todos los metadatos requeridos, condiciones de acceso y redistribución y procedencia; un dataset inexistente produce un error de no encontrado |
| FDH-001-AC-15 | FR-04 | La API no ofrece operaciones que modifiquen datos y permite consultar el estado de las ejecuciones |
| FDH-001-AC-16 | FR-05 | El portal muestra estados distintos de carga mientras espera, vacío cuando no hay registros y fallido cuando la API devuelve error o no responde |
| FDH-001-AC-17 | FR-05 | El portal muestra los mismos registros que la API y distingue ejecuciones `running`, `succeeded`, `partial` y `failed` |
| FDH-001-AC-18 | FR-05, NFR-02 | El detalle del portal muestra licencia, estado de revisión, acceso, redistribución, procedencia y fecha de verificación, con lo desconocido visible como tal |
| FDH-001-AC-19 | FR-01, FR-03, FR-04, FR-05 | Dadas las dos fuentes verificadas en vivo, el descubrimiento obtiene metadatos reales y los mismos registros publicables aparecen en la API y el portal |
| FDH-001-AC-20 | FR-06 | Antes de implementar el adaptador de World Bank, `research/` documenta su API oficial, condiciones y pruebas en vivo; si no es viable, existe una solicitud de alternativa y no se sustituye sin aprobación |
| FDH-001-AC-21 | FR-06 | El adaptador de Data360 solicita solo entradas de tipo dataset, cumple el mismo contrato y sus registros aparecen en la misma API y portal sin modificar el núcleo del catálogo |
| FDH-001-AC-22 | NFR-01 | Un intento que supera el tiempo configurado (10 segundos por defecto) se cancela; un error reintentable produce como máximo 4 intentos con esperas crecientes y no inferiores a `Retry-After`; si este supera 60 segundos no hay más intentos |
| FDH-001-AC-23 | NFR-01 | Las respuestas HTTP 400, 401, 403 y 404 producen un único intento |
| FDH-001-AC-24 | NFR-01 | Los logs identifican la ejecución y, en pruebas con credenciales ficticias, no las contienen; el repositorio no contiene secretos |
| FDH-001-AC-25 | NFR-01 | Con la configuración documentada, API, portal y base de datos solo aceptan conexiones desde el equipo local |
| FDH-001-AC-26 | NFR-02 | Cada fuente registra URL oficial y fecha de verificación; todo dataset nuevo queda `pending`, con acceso y redistribución por separado y sin permisos inferidos |
| FDH-001-AC-27 | NFR-02 | Los metadatos de una fuente `undetermined` o `denied`, y los de datasets `restricted` aunque su fuente sea `allowed`, no aparecen en búsquedas ni detalles; los `pending` de una fuente `allowed` aparecen identificados como pendientes |
| FDH-001-AC-28 | NFR-03 | Desde un clon limpio, los comandos documentados ejecutan sin red las pruebas de paginación, deduplicación, fallos, reintentos, estados de ejecución y filtros |
| FDH-001-AC-29 | NFR-03 | Cada prueba en vivo registra fecha UTC, solicitud, versión del código y resultado, incluidos los fallos |
| FDH-001-AC-30 | FR-03, FR-04, FR-05 | Si la fuente indica más resultados tras el máximo de páginas de una consulta, la ejecución registra para ella `truncated` y el total declarado si lo hay, sin registrar un error; sin fallos ni rechazos queda `succeeded`, y la API y el portal muestran el truncamiento |
| FDH-001-AC-31 | FR-04, FR-05, NFR-02 | La API y el portal muestran para cada dataset la atribución de su fuente y todas sus licencias declaradas, con enlace y requisito de cita si existen; una licencia externa se muestra como tal y una ausente como desconocida |
| FDH-001-AC-32 | FR-03 | Si todos los registros recuperados se rechazan por errores de validación, la ejecución queda `failed` con su conteo y los datos anteriores no cambian |
| FDH-001-AC-33 | FR-06 | Cada adaptador declara sus capacidades, y una configuración que exija una no soportada se rechaza sin enviar ninguna solicitud |
| FDH-001-AC-34 | FR-06 | Las pruebas de cada adaptador se ejecutan con respuestas sintéticas, sin red ni base de datos |
| FDH-001-AC-35 | NFR-02 | Ni declarar `allowed` los metadatos de una fuente ni la licencia declarada cambian los permisos de extracción y redistribución, `undetermined` por defecto; los permisos solo cambian por configuración o comando local, con evidencia y fecha |
| FDH-001-AC-36 | FR-03 | Cada localizador conserva tipo, URL, campo de origen y estado; se aceptan tipos nuevos, una URL no HTTPS o mal formada queda `invalid` sin rechazar ni eliminar el dataset, no figura entre las utilizables para extracción hasta que una versión corregida supere la validación, y ninguna se consulta |
| FDH-001-AC-37 | NFR-03 | Un cambio publicado en la rama o propuesto en un PR ejecuta en GitHub Actions las pruebas sin red y los controles definidos en el plan, y un fallo es visible |

## Fuera de alcance

Ingesta masiva de datos financieros, pipelines programados, integración de dlt o Dagster, analítica financiera y despliegue productivo. Son incrementos posteriores (ver [roadmap](../../ROADMAP.md)). Las demás fuentes del inventario tampoco entran en FDH-001.

## Puntos abiertos

Son decisiones de diseño que resuelve el plan; no cambian los requisitos anteriores.

1. ¿Los permisos y estados de revisión se administran con un archivo de configuración, un comando local o ambos?
2. ¿Qué campo de Data360 se usa como URL oficial y como publicador?
3. ¿La paginación de Socrata usa desplazamiento o cursor? Con desplazamiento se observó un registro repetido entre páginas.
4. ¿Qué controles de integración continua se incluyen además de las pruebas?
