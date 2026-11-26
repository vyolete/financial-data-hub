# ADR-0002: Monolito modular y frontend desacoplado

- **Fecha**: 2026-11-25
- **Estado**: Accepted (registro verificable en GitHub pendiente)
- **Autoridad**: aprobada por la dirección del proyecto en sesión de trabajo del 2026-11-25.
  El registro verificable es un comentario personal de la persona mantenedora en el
  [issue #2](https://github.com/vyolete/financial-data-hub/issues/2); aún no consta.
- **Complementado por**: [ADR-0006](0006-metadata-driven-architecture.md) (planos de control y datos).

## Contexto

La visión pide minimizar recursos y evitar microservicios prematuros.

## Alternativas

Microservicios o un backend gestionado por la herramienta de frontend. No hay evaluación
comparativa documentada.

## Decisión

- Un único backend desplegable, organizado en módulos con interfaces explícitas.
- Frontend separado que consume solo la API HTTP documentada.
- Lovable apoya el desarrollo del frontend. El backend permanece independiente de Lovable.

## Consecuencias

- Los contratos de la API se definen antes de integrar el frontend.
- El frontend no accede a PostgreSQL ni introduce un backend alternativo.
- El código generado con Lovable cumple las mismas revisiones, pruebas y reglas de seguridad.

## Pendiente

- Estructura de directorios (se define en el plan de FDH-001).
- Verificar cómo sincroniza Lovable con GitHub: repositorio y rama que usa, permisos que pide y
  tecnologías que genera. No usarlo sobre este repositorio hasta comprobar que respeta las ramas
  aisladas y la aprobación humana.
