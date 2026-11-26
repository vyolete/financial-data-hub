# Contrato de la línea de comandos

Comando `fdh`, ejecutable local y dentro de la imagen del backend. Requisitos: FR-01, FR-03, NFR-01, NFR-02.

| Comando | Efecto |
|---|---|
| `fdh config check [--config PATH]` | Valida la configuración sin red ni base de datos |
| `fdh sources sync [--config PATH]` | Aplica fuentes y permisos de publicación usando solo la base de datos; sin solicitudes externas |
| `fdh discover (--source ID \| --all) [--config PATH]` | Ejecuta el descubrimiento |
| `fdh runs list [--source ID] [--limit N]` | Muestra ejecuciones |
| `fdh dataset show --source ID --external-id ID` | Muestra un dataset, también si está oculto en la API |
| `fdh dataset review --source ID --external-id ID --status pending\|verified\|restricted --evidence TEXT --by NAME --on DATE` | Cambia el estado de revisión |
| `fdh dataset permission --source ID --external-id ID [--extraction VALUE] [--redistribution VALUE] --evidence TEXT --by NAME --on DATE` | Cambia permisos, con `allowed`, `denied` o `undetermined` |
| `fdh dataset conditions --source ID --external-id ID [--access TEXT] [--redistribution TEXT] --evidence TEXT --by NAME --on DATE` | Registra condiciones |

## Reglas
- `--evidence`, `--by` y `--on` son obligatorios y no admiten valores vacíos.
- Cada cambio escribe en la bitácora de decisiones en la misma transacción.
- Para revocar la publicación de una fuente: cambiar `metadata_publication` y ejecutar `fdh sources sync`. Para ocultar un dataset: `fdh dataset review --status restricted`. Ninguno depende de un descubrimiento ni de servicios externos.
- `--limit` va de 1 a 100; predeterminado 20.
- La salida va a `stdout`; los logs JSON, a `stderr`. Ninguna contiene secretos.

## Códigos de salida

| Código | Significado |
|---|---|
| 0 | Éxito; en `discover`, todas las ejecuciones `succeeded` |
| 1 | Error de ejecución del comando, por ejemplo base de datos no disponible |
| 2 | Uso o configuración no válidos; sin solicitudes de red |
| 3 | Alguna ejecución `partial` y ninguna `failed` |
| 4 | Alguna ejecución `failed` |
| 5 | Ya hay una ejecución en curso para la fuente |

Con `--all`, una fuente fallida no impide ejecutar las demás y se devuelve el resultado más grave, en este orden: 1, 4, 5, 3 y 0.

`discover` devuelve 2, sin solicitudes ni cambios en la base de datos, si la fuente no existe o si alguna fuente seleccionada no tiene adaptador.

## Salida

`discover` imprime por fuente el identificador y estado de la ejecución, solicitudes enviadas (reintentos incluidos), páginas, registros recibidos, únicos, creados, actualizados, sin cambios y rechazados, fallos, duración total y de persistencia, cada consulta con su total declarado y truncamiento, motivos de rechazo y errores. El número de solicitudes, los motivos de rechazo y el tiempo de persistencia constan en la salida y en los logs, no en la base de datos.

`runs list` imprime una línea por ejecución, la más reciente primero, con sus conteos, consultas truncadas y duración, seguida de sus errores.
