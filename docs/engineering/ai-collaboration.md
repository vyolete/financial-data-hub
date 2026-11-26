# Colaboración entre agentes

Claude Code, ChatGPT y Gemini pueden investigar, diseñar, implementar o revisar según sus capacidades y permisos. Lovable podrá consumir contratos aprobados para el portal. Los roles no son exclusivos.

AGENTS.md contiene instrucciones comunes; CLAUDE.md y GEMINI.md son adaptadores. Cada agente debe leer los documentos aplicables y comprobar la revisión de Git utilizada. En interfaces web o Colab, cargar contexto explícitamente si no se importa automáticamente.

No asumir sincronización de memorias privadas, acceso a GitHub, ejecución de pruebas ni permisos. Usar ramas o worktrees aislados, evitar cambios concurrentes sobre los mismos archivos y coordinar mediante issues y PR. El mantenedor aprueba cambios de alcance, decisiones y fusiones.

MCP, skills y subagentes podrán evaluarse cuando exista necesidad; no son requisitos iniciales.
