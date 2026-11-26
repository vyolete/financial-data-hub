# Transferencia de trabajo

Registrar en el issue o PR correspondiente, sin duplicar el estado en múltiples archivos. Usar esta plantilla:

```yaml
task_id: null
specification: null
agent: null
timestamp_utc: null
branch: null
commit: null            # SHA completo
pushed: null            # true si el commit está disponible en el remoto
working_tree: null      # clean, o lista de archivos modificados y sin seguimiento
feature_directory: null # valor de .specify/feature.json
environment: {}         # versiones relevantes de las herramientas
status: pending
work_completed: []
validation:
  tests_executed: []    # comando, código de salida y resultado
  tests_not_executed: [] # prueba y motivo
  evidence: []
approvals: []           # enlaces a registros humanos en GitHub
blockers: []
decisions: []
next_action: null
```

Un trabajo es reproducible cuando el commit está en el remoto y el árbol está limpio. En caso contrario, declararlo y explicar cómo recuperar los cambios; los cambios sin push solo existen en el equipo de origen.

El agente receptor verifica la revisión, lee las referencias, repite las comprobaciones de las que dependa y confirma alcance y bloqueos. No interpretar una afirmación de éxito como evidencia sin comprobarla. Un handoff no concede permisos ni sustituye una aprobación. No incluir secretos, datos personales ni logs sin sanitizar.
