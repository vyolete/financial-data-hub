# Financial Data Hub

Plataforma de ingeniería de datos financieros y económicos, con un motor modular de integración ETL/ELT como componente central. Proyecto público en construcción: en local ya descubre y registra metadatos de datasets de Datos Abiertos Colombia desde la línea de comandos; todavía no hay API ni portal de catálogo.

## Propósito
Facilitar el acceso reproducible a fuentes públicas, con trazabilidad, calidad, eficiencia y contratos verificables. Los consumidores previstos incluyen Python, R, Power BI y un portal web.

## Arranque local
Requiere Docker y unos 3 GB libres.

```bash
cp .env.example .env        # definir POSTGRES_PASSWORD
docker compose up --detach --build --wait
./scripts/smoke.sh
docker compose run --rm api fdh sources sync
docker compose run --rm api fdh discover --source co-datos-gov   # solicitudes reales
```

Portal en <http://127.0.0.1:8080> y API en <http://127.0.0.1:8000/health>, solo accesibles desde el equipo. Detener con `docker compose down`. Pruebas y más comandos en la [guía de validación](specs/001-source-discovery/quickstart.md).

## Navegación
- [Visión](docs/product/vision.md)
- [Arquitectura objetivo](docs/architecture/target-architecture.md)
- [Estructura del repositorio: actual y objetivo](docs/architecture/repository-structure.md)
- [Inventario de fuentes](research/sources/inventory.md)
- [Roadmap](ROADMAP.md)
- [Documentación](docs/README.md)
- [Especificaciones](specs/README.md)
- [Investigación](research/README.md)
- [Instrucciones para agentes](AGENTS.md)
- [Contribución](CONTRIBUTING.md)
- [Seguridad](SECURITY.md)

## Estado
FDH-001 en implementación: [especificación](specs/001-source-discovery/spec.md) aprobada y entregas E0 y E1 construidas. Decisiones de framework SDD, arquitectura, stack, licencia e idioma en los [ADR](docs/adr/README.md); principios en la [constitución](.specify/memory/constitution.md).

## Licencia
Software bajo [Apache License 2.0](LICENSE). La licencia no cubre datos de terceros. No se publican datos externos sin revisar sus condiciones.
