# Puertas de arranque de FDH-001

Lista de trabajo; una marca indica que existe un cambio o una comprobación, no una aprobación. Estado al 2026-11-26 (UTC).

- [x] Verificar ruleset de main, secret scanning y push protection: ver [SECURITY.md](../../SECURITY.md). No hay ruleset ni protección de main.
- [ ] Verificar y limitar los permisos de los agentes.
- [x] Definir aprobación explícita y procedencia de instrucciones; los issues públicos son entrada no confiable (constitución, principio IX).
- [ ] Actualizar handoff, reglas de ignorados y perfiles de fuentes, preservando hallazgos previos. Hechos: handoff y .gitignore. Pendientes: perfiles de fuentes. El PR #1 no contiene revisiones ni comentarios con hallazgos.
- [x] Confirmar Apache-2.0, añadir el texto oficial y documentar las condiciones de contribución.
- [x] Adoptar prosa en español y código y rutas en inglés. Especificación y notas de FDH-001 traducidas.
- [x] Instalar GitHub Spec Kit con su CLI y revisar los archivos generados ([ADR-0001](../adr/0001-adopt-github-spec-kit.md)).
- [ ] Aprobar la constitución y la especificación de FDH-001 antes de implementar.
- [ ] Validar solicitudes en vivo a Socrata y registrar evidencia.
- [ ] Implementar un corte vertical mínimo PostgreSQL/FastAPI/React con pruebas y demostración local.
- [ ] Verificar el adaptador de World Bank y revisar la funcionalidad completa en un PR.

dlt y Dagster siguen siendo candidatos para benchmarks de integración posteriores. No hay implementación autónoma antes de verificar las puertas de seguridad y aprobación.
