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
- Q: ¿Qué metadatos y filtros se requieren? → A: Identificador externo, título, descripción, proveedor, plataforma, publicador, categoría original, etiquetas, URL oficial, fechas disponibles, licencia, estado de verificación y procedencia. Filtros por texto, proveedor y categoría.
- Q: ¿Cómo se representan licencia y acceso? → A: Estados de revisión `pending`, `verified` y `restricted`. Condiciones de acceso y de redistribución por separado. La disponibilidad pública no implica permisos. Los metadatos pendientes se muestran cuando su publicación está permitida.
- Q: ¿Qué hacen la API y el portal con los metadatos de una fuente cuyo permiso de publicación no se ha determinado? → A: Ocultarlos. Cada fuente declara el permiso tras revisar sus condiciones; sin esa declaración no se muestran.
- Q: ¿Cuál es el papel de World Bank? → A: Segundo adaptador para demostrar la extensibilidad del catálogo, tras investigar su API oficial y condiciones de uso. Si no es viable, se registra evidencia y se solicita aprobación de una alternativa.
- Q: ¿Se completan los criterios de aceptación? → A: Sí, para todos los requisitos, incluidos procedencia, detalle, estados de interfaz, reintentos, logs, fechas de verificación, deduplicación y fallos parciales.

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

Datasets de fuentes distintas son registros distintos, aunque compartan identificador externo.

## Requisitos

- **FDH-001-FR-01**: Descubrir datasets mediante la Socrata Discovery API, con un comando local bajo demanda, consultas configurables y paginación acotada. La fuente inicial es `www.datos.gov.co` y solo se incluyen datasets. Dominios, términos y límites son configurables.
- **FDH-001-FR-02**: Deduplicar por fuente e identificador externo, y conservar la procedencia y el historial de búsquedas. Repetir el descubrimiento actualiza los metadatos. Un dataset que deja de aparecer no se elimina automáticamente.
- **FDH-001-FR-03**: Persistir en PostgreSQL los metadatos y los registros de ejecución; repetir el descubrimiento no debe duplicar datasets.
  - Metadatos: identificador externo, título, descripción, proveedor, plataforma, publicador, categoría original, etiquetas, URL oficial, fechas disponibles, licencia, estado de verificación y procedencia. Un valor ausente se registra como desconocido.
  - Ejecución: identificador, fuente, parámetros, inicio y fin en UTC, estado, páginas procesadas, conteos (recibidos, creados, actualizados y rechazados) y errores sanitizados.
  - Estados: `running`, `succeeded` (se procesaron todas las páginas solicitadas, aunque no haya resultados), `partial` (se procesó al menos una página y otra falló) y `failed` (no se procesó ninguna).
- **FDH-001-FR-04**: Exponer mediante FastAPI, en modo de solo lectura, búsqueda paginada, filtros por texto, proveedor y categoría, detalle de datasets y estado de las ejecuciones. Página predeterminada de 20 registros y máxima de 100.
- **FDH-001-FR-05**: Mostrar en un portal React de solo lectura los registros reales del catálogo y el estado de las ejecuciones; distinguir los estados vacío, cargando y fallido, y no presentar una ejecución `partial` o `failed` como exitosa.
- **FDH-001-FR-06**: Añadir World Bank como segundo adaptador de descubrimiento, tras verificar su API oficial y condiciones, sin modificar el núcleo del catálogo, que no depende de Socrata. Si no es viable, registrar la evidencia y solicitar aprobación de una alternativa.
- **FDH-001-NFR-01**: Solicitudes acotadas, tiempo de espera, política de reintentos, logs sanitizados y ningún secreto en Git.
  - Tiempo de espera de 10 segundos y máximo 3 reintentos (4 intentos en total), con espera creciente y respeto de `Retry-After`.
  - Se reintentan fallos de conexión, tiempos de espera y respuestas HTTP 429, 500, 502, 503 y 504; los demás errores no se reintentan.
  - API, portal y base de datos sin autenticación solo son accesibles desde el equipo local.
- **FDH-001-NFR-02**: Registrar URL oficial de la fuente, fecha de verificación y estado de acceso y redistribución; las condiciones desconocidas siguen siendo desconocidas.
  - Estado de revisión: `pending` (predeterminado), `verified` o `restricted`. Cambiarlo requiere una revisión humana con evidencia y fecha.
  - Las condiciones de acceso y de redistribución se registran por separado. La disponibilidad pública no implica permisos.
  - Cada fuente tiene un permiso de publicación de metadatos: `allowed`, `denied` o `undetermined` (predeterminado). Una persona lo declara con evidencia y fecha. La API y el portal solo muestran metadatos de fuentes `allowed`.
- **FDH-001-NFR-03**: Pruebas y evidencias reproducibles; sin resultados inventados. Las pruebas automatizadas no dependen de la red y usan datos sintéticos identificados; las pruebas en vivo se ejecutan y documentan por separado.

## Límites configurables

| Límite | Valor inicial |
|---|---|
| Registros por página solicitada a la fuente | 100 |
| Páginas por consulta | 5 |
| Tiempo de espera por solicitud | 10 s |
| Reintentos por solicitud | 3 |
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
| FDH-001-AC-07 | FR-03 | Cada dataset persistido conserva los metadatos requeridos y su procedencia; los valores ausentes figuran como desconocidos |
| FDH-001-AC-08 | FR-03 | Si una página se procesa y otra falla, los registros válidos permanecen, la ejecución queda `partial` con páginas procesadas y errores, y repetirla no crea duplicados |
| FDH-001-AC-09 | FR-03 | Si no se procesa ninguna página, la ejecución queda `failed`, los datos anteriores no cambian y ni la API ni el portal indican éxito |
| FDH-001-AC-10 | FR-03 | Una búsqueda sin resultados y sin errores queda `succeeded` con cero registros |
| FDH-001-AC-11 | FR-03 | Un registro inválido se cuenta como rechazado y se informa, sin impedir que se guarden los válidos |
| FDH-001-AC-12 | FR-04 | Sin indicar tamaño, la API devuelve como máximo 20 registros; permite solicitar hasta 100 y nunca devuelve más de 100 |
| FDH-001-AC-13 | FR-04 | Los filtros por texto, proveedor y categoría funcionan por separado y combinados, y sin coincidencias devuelven una colección vacía |
| FDH-001-AC-14 | FR-04 | El detalle devuelve todos los metadatos requeridos, condiciones de acceso y redistribución y procedencia; un dataset inexistente produce un error de no encontrado |
| FDH-001-AC-15 | FR-04 | La API no ofrece operaciones que modifiquen datos y permite consultar el estado de las ejecuciones |
| FDH-001-AC-16 | FR-05 | El portal muestra estados distintos de carga mientras espera, vacío cuando no hay registros y fallido cuando la API devuelve error o no responde |
| FDH-001-AC-17 | FR-05 | El portal muestra los mismos registros que la API y distingue ejecuciones `running`, `succeeded`, `partial` y `failed` |
| FDH-001-AC-18 | FR-05, NFR-02 | El detalle del portal muestra licencia, estado de revisión, acceso, redistribución, procedencia y fecha de verificación, con lo desconocido visible como tal |
| FDH-001-AC-19 | FR-01, FR-03, FR-04, FR-05 | Dada una fuente verificada en vivo, el descubrimiento obtiene metadatos reales y los mismos registros aparecen en la API y el portal |
| FDH-001-AC-20 | FR-06 | Antes de implementar el adaptador de World Bank, `research/` documenta su API oficial, condiciones y pruebas en vivo; si no es viable, existe una solicitud de alternativa y no se sustituye sin aprobación |
| FDH-001-AC-21 | FR-06 | El segundo adaptador cumple el mismo contrato y sus registros aparecen en la misma API y portal sin modificar el núcleo del catálogo |
| FDH-001-AC-22 | NFR-01 | Una solicitud que supera 10 segundos se cancela; un error reintentable produce como máximo 4 intentos con esperas crecientes y no inferiores a `Retry-After` |
| FDH-001-AC-23 | NFR-01 | Las respuestas HTTP 400, 401, 403 y 404 producen un único intento |
| FDH-001-AC-24 | NFR-01 | Los logs identifican la ejecución y, en pruebas con credenciales ficticias, no las contienen; el repositorio no contiene secretos |
| FDH-001-AC-25 | NFR-01 | Con la configuración documentada, API, portal y base de datos solo aceptan conexiones desde el equipo local |
| FDH-001-AC-26 | NFR-02 | Cada fuente registra URL oficial y fecha de verificación; todo dataset nuevo queda `pending`, con acceso y redistribución por separado y sin permisos inferidos |
| FDH-001-AC-27 | NFR-02 | Los metadatos de una fuente `undetermined` o `denied` no aparecen en búsquedas ni detalles; al declararla `allowed`, los `pending` aparecen identificados como pendientes |
| FDH-001-AC-28 | NFR-03 | Desde un clon limpio, los comandos documentados ejecutan sin red las pruebas de paginación, deduplicación, fallos, reintentos, estados de ejecución y filtros |
| FDH-001-AC-29 | NFR-03 | Cada prueba en vivo registra fecha UTC, solicitud, versión del código y resultado, incluidos los fallos |

## Fuera de alcance

Ingesta masiva de datos financieros, pipelines programados, integración de dlt o Dagster, analítica financiera y despliegue productivo. Son incrementos posteriores.

## Puntos abiertos

No cambian los requisitos anteriores. Se resuelven antes de aprobar o, si se indica, en el plan.

1. ¿Se muestran los metadatos de un dataset `restricted` cuando su fuente es `allowed`?
2. ¿Dónde registra una persona el estado de revisión y el permiso de publicación, dado que la API y el portal son de solo lectura? (plan)
3. ¿Hace que una ejecución sea `partial` la presencia de registros rechazados sin páginas fallidas?
4. ¿Qué ocurre si `Retry-After` pide una espera mayor que la aceptable para el comando?
