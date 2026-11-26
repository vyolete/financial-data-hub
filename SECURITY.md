# Seguridad

No publicar credenciales, tokens, archivos .env reales, información personal, datos restringidos ni respuestas o logs sin revisar. Usar secretos del entorno y permisos mínimos. Revisar notebooks y su salida antes de publicar. Los ejemplos de configuración (`.env.example`) no contienen valores reales.

## Si se expone un secreto
1. Revocar o rotar la credencial de inmediato; borrarla de un archivo o del historial no basta.
2. Avisar a la persona mantenedora por un canal privado, sin repetir el valor.
3. Limpiar el historial solo con autorización expresa.

## Agentes
Usar credenciales propias de alcance mínimo cuando sea posible. Un agente que opere con las credenciales de la persona mantenedora no adquiere su autoridad.

## Controles de GitHub
Consultados mediante la API de GitHub el 2026-11-26 (UTC). Es una fotografía de esa fecha; volver a verificar antes de depender de ella.

| Control | Estado observado |
|---|---|
| Secret scanning | Activo |
| Push protection | Activo |
| Secret scanning de patrones genéricos y comprobación de validez | Inactivo |
| Actualizaciones de seguridad de Dependabot | Inactivo |
| Protección de la rama main y rulesets | No configurados |
| Reporte privado de vulnerabilidades | Inactivo |

Secret scanning y push protection no detectan cualquier secreto; la revisión del diff sigue siendo necesaria.

## Reporte de vulnerabilidades
Reportar de forma privada mediante el mecanismo de reporte de GitHub si está habilitado; de lo contrario solicitar al mantenedor un canal privado sin revelar detalles en issues públicos. La habilitación del mecanismo y la política de versiones soportadas están pendientes. No existe todavía una versión operativa.
