# ADR-0005: Idioma y memoria compartida

- **Fecha**: 2026-11-25
- **Estado**: Accepted (registro verificable en GitHub pendiente)
- **Autoridad**: aprobada por la dirección del proyecto en sesión de trabajo del 2026-11-25.
  El registro verificable es un comentario personal de la persona mantenedora en el
  [issue #2](https://github.com/vyolete/financial-data-hub/issues/2); aún no consta.

## Contexto

Colaboran ChatGPT, Claude y Gemini, que no comparten memoria interna.

## Decisión

- Documentación en español.
- Código, rutas, identificadores y contratos en inglés.
- GitHub como memoria compartida: archivos versionados, issues y PR.

## Consecuencias

- La memoria privada de un agente no es normativa.
- Los encabezados y palabras clave que fija Spec Kit pueden conservarse en inglés.
- La especificación y las notas de investigación de FDH-001, redactadas en inglés, se traducen en
  un cambio que preserve su alcance, antes de aprobar la especificación.
- Autoridad, aprobación y transferencia se rigen por el principio IX de la
  [constitución](../../.specify/memory/constitution.md).
