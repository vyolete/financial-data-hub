# Transferencia de trabajo

Registrar en el issue o PR correspondiente, sin duplicar el estado en múltiples archivos. Usar esta plantilla:

```yaml
task_id: null
specification: null
agent: null
branch: null
commit: null
status: pending
work_completed: []
validation:
  tests_executed: []
  tests_not_executed: []
  evidence: []
blockers: []
decisions: []
next_action: null
```

El agente receptor verifica la revisión, lee las referencias y confirma alcance y bloqueos. No interpretar una afirmación de éxito como evidencia sin comprobarla. No incluir secretos, datos personales ni logs sin sanitizar.
