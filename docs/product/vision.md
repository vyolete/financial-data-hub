# Visión del producto

Financial Data Hub es una plataforma de ingeniería de datos financieros y económicos para analistas, investigadores, docentes, estudiantes y desarrolladores. Su componente central es un motor modular de integración ETL/ELT. El catálogo es uno de sus componentes, no el producto completo.

La plataforma debe permitir descubrir, configurar, extraer, transformar, almacenar, automatizar, consultar y distribuir datos financieros, garantizando calidad, trazabilidad, eficiencia y confiabilidad.

## Capacidades previstas
Descubrimiento y catálogo de fuentes; conectores reutilizables (Socrata, REST, SDMX, archivos y especializados); extracción por lotes e incremental; validación, normalización, historial de revisiones y linaje; capas lógicas Bronze/Silver/Gold; automatización; analítica; servicios de consulta y exportación para Python, R, Power BI y un portal independiente. El diseño está en la [arquitectura objetivo](../architecture/target-architecture.md).

## Fuentes
Fuentes colombianas, internacionales y de mercados, además de archivos CSV, Excel y Parquet. Son candidatas hasta contar con evidencia: ver el [inventario](../../research/sources/inventory.md).

## Restricciones
Respetar licencias y privacidad, minimizar recursos, preservar procedencia, evitar microservicios prematuros, reutilizar capacidades existentes de forma justificada y diseñar observabilidad y recuperación desde el inicio.

## Alcance inicial
Descubrimiento y catálogo reproducibles sobre Socrata (Datos Abiertos Colombia) y World Bank (FDH-001), con contratos pensados para el futuro motor de integración. El stack base está decidido ([ADR-0003](../adr/0003-technology-stack.md)); las demás tecnologías se evalúan mediante evidencia antes de elegirlas. No se promete cobertura universal, datos en tiempo real ni asesoramiento financiero.

## Éxito
Fuentes verificadas, requisitos trazables, ejecuciones reproducibles, errores visibles y contratos comprobables. Umbrales cuantitativos se definirán en las especificaciones correspondientes.
