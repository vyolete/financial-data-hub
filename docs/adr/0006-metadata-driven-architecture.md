# ADR-0006: Arquitectura orientada a metadatos

- **Fecha**: 2026-11-25
- **Estado**: Accepted (registro verificable en GitHub pendiente)
- **Autoridad**: aprobada por la mantenedora en sesión de trabajo del 2026-11-25. El registro
  verificable es un comentario personal suyo en el
  [issue #2](https://github.com/vyolete/financial-data-hub/issues/2); aún no consta.

## Contexto

El producto es una plataforma de ingeniería de datos financieros cuyo núcleo es un motor modular
de integración ETL/ELT. El catálogo es uno de sus componentes.

## Alternativas y evidencia

No hay comparativa ni prueba técnica documentada de la arquitectura.

## Decisión

- Monolito modular orientado a metadatos, con separación lógica entre plano de control y plano de
  datos. Mantiene [ADR-0002](0002-modular-monolith.md).
- Capas Bronze (originales), Silver (normalizados y validados) y Gold (productos y vistas).
- Familias de conectores: Socrata, REST, SDMX, archivos y adaptadores especializados.
- Parquet y almacenamiento de objetos junto a PostgreSQL; DuckDB como alternativa analítica por
  evaluar.
- GitHub Actions para integración continua. Observabilidad progresiva: logs, métricas y después
  herramientas especializadas.

El detalle de componentes, responsabilidades y flujos está en la
[arquitectura objetivo](../architecture/target-architecture.md).

## Consecuencias

- La configuración y el estado se modelan como datos antes de automatizar.
- La separación de planos no autoriza procesos desplegables nuevos: cada uno requiere un ADR.
- Cada capacidad llega con su funcionalidad del [roadmap](../../ROADMAP.md); nada se construye
  por adelantado.

## Pendiente

Producto de almacenamiento de objetos, evaluación de DuckDB y herramientas de observabilidad.
