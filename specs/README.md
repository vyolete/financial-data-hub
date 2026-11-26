# Especificaciones

Cada funcionalidad tendrá un identificador estable y requisitos verificables. Estructura de GitHub Spec Kit: spec.md, research.md (referencias a evidencia), plan.md, tasks.md, checklists y contratos locales cuando se justifiquen. Los contratos compartidos aprobados residirán en contracts/ cuando exista.

Las especificaciones deben identificar alcance, exclusiones, escenarios, requisitos funcionales y no funcionales, criterios de aceptación y estado. Mantenerlas vigentes al cambiar comportamiento.

## Funcionalidades
| ID | Directorio |
|---|---|
| FDH-001 | [001-source-discovery](001-source-discovery/spec.md) |

## Vincular la funcionalidad activa
Spec Kit lee `.specify/feature.json`, que es local y no se versiona. En cada copia de trabajo, desde la raíz (Bash):

```bash
bash -c 'source .specify/scripts/bash/common.sh && SPECIFY_FEATURE_DIRECTORY=specs/001-source-discovery get_feature_paths'
```

Comprobar sin modificar archivos:

```bash
.specify/scripts/bash/check-prerequisites.sh --json --paths-only
```

No ejecutar `speckit-specify` para una funcionalidad existente sin indicar su directorio: puede crear una especificación duplicada.
