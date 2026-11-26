# ADR-0001: Adoptar GitHub Spec Kit

- **Fecha**: 2026-11-25
- **Estado**: Accepted
- **Autoridad**: aprobada por la dirección del proyecto en sesión de trabajo del 2026-11-25.
  Registro verificable: [comentario en el issue #2](https://github.com/vyolete/financial-data-hub/issues/2#issuecomment-7179859703) sobre el commit
  `afe2090dda25295a98164c507a99cc52d3644ec1` (2026-11-26 UTC).

## Contexto

El proyecto requiere un flujo Spec-Driven Development común a varios agentes.

## Alternativas

OpenSpec figuraba como opción. No hay evaluación comparativa documentada.

## Decisión

Adoptar GitHub Spec Kit 1.1.2, con la integración `claude` y scripts `sh`. La constitución vive en
`.specify/memory/constitution.md` y las especificaciones en `specs/`.

### Qué se versiona

| Ruta | Tratamiento | Motivo |
|---|---|---|
| `.specify/memory/` | Versionar | Constitución y referencia de su plantilla |
| `.specify/scripts/`, `.specify/templates/`, `.specify/workflows/` | Versionar | Flujo reproducible |
| `.specify/integrations/`, `integration.json`, `init-options.json` | Versionar | Versión y hashes de la instalación |
| `.specify/.gitignore` | Versionar | Excluye el estado local |
| `.claude/skills/speckit-*/` | Versionar | Habilidades compartidas |
| `.specify/feature.json` | Local, ignorado | Puntero a la funcionalidad activa en cada copia |
| `.specify/extensions/*/local-config.yml` | Local, ignorado | Ajustes por equipo |
| `.claude/settings.local.json`, `CLAUDE.local.md` | Local, ignorado | Permisos y preferencias personales |

Cualquier otro contenido nuevo en `.claude/` se revisa antes de versionarlo.

## Consecuencias

- Cada copia de trabajo vincula la funcionalidad activa (ver `specs/README.md`).
- Solo está instalada la integración de Claude. ChatGPT y Gemini usan los documentos del
  repositorio; instalar sus integraciones es una decisión pendiente.
- Los archivos generados no se editan a mano; las actualizaciones se hacen con la CLI y se revisan.
- La plantilla de tareas trata las pruebas como opcionales. Prevalece el principio VIII de la
  constitución: cada especificación y plan las exigen.

## Referencias

`.specify/integrations/speckit.manifest.json`, `.specify/integrations/claude.manifest.json`.
