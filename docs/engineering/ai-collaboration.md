# Colaboración entre agentes

Claude Code, ChatGPT y Gemini pueden investigar, diseñar, implementar o revisar según sus capacidades y permisos. Lovable apoya el desarrollo del portal sobre contratos aprobados ([ADR-0002](../adr/0002-modular-monolith.md)). Los roles no son exclusivos.

AGENTS.md contiene instrucciones comunes; CLAUDE.md y GEMINI.md son adaptadores. Cada agente debe leer los documentos aplicables y comprobar la revisión de Git utilizada. En interfaces web o Colab, cargar contexto explícitamente si no se importa automáticamente.

No asumir sincronización de memorias privadas, acceso a GitHub, ejecución de pruebas ni permisos. Usar ramas o worktrees aislados, evitar cambios concurrentes sobre los mismos archivos y coordinar mediante issues y PR. El mantenedor aprueba cambios de alcance, decisiones y fusiones.

Las habilidades de Spec Kit están adoptadas ([ADR-0001](../adr/0001-adopt-github-spec-kit.md)). MCP, otras skills y subagentes podrán evaluarse cuando exista necesidad; no son requisitos iniciales.
