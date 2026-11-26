# ADR-0009: Proveedor de nube y modelo de ejecución para el despliegue

- **Fecha**: 2026-11-26
- **Estado**: Proposed
- **Autoridad**: ninguna todavía. Requiere el registro de aprobación de la mantenedora (constitución IX).
- **Relacionado**: [FDH-009](../../specs/009-cloud-platform/spec.md), [ADR-0002](0002-modular-monolith.md), [ADR-0003](0003-technology-stack.md), [ADR-0006](0006-metadata-driven-architecture.md)

## Contexto

El sistema tiene un único backend desplegable (API y CLI en la misma imagen), un portal estático servido por nginx y PostgreSQL 18. Hoy solo corre en Docker Compose. FDH-009 necesita un entorno de nube con:

- la API y el portal disponibles con tráfico bajo;
- tareas bajo demanda con la misma imagen (migraciones y descubrimiento);
- PostgreSQL 18 administrado;
- acceso restringido a identidades autorizadas, porque la API no tiene autenticación;
- costo acotado.

El ADR-0002 descarta un backend gestionado por la herramienta de frontend. Supabase solo puede entrar como PostgreSQL administrado, y en ese rol compite con los servicios equivalentes de cada nube.

## Criterios

1. Ejecutar la misma imagen como servicio HTTP y como tarea, sin código específico del proveedor (FDH-009-NFR-06).
2. Restringir el acceso por identidad sin cambiar el código (FDH-009-FR-10).
3. PostgreSQL 18 administrado, sin acceso público.
4. Costo base mensual con tráfico bajo.
5. Número de componentes que operar.
6. Federación OIDC con GitHub Actions y un proveedor de OpenTofu/Terraform maduro.
7. Experiencia de quien opera la infraestructura.
8. Camino hacia el almacenamiento de objetos con API compatible con S3, que se decidirá en FDH-004.

## Alternativas

Evidencia de precios y capacidades: [informe de costos](../../research/benchmarks/cloud-platform-costs/README.md). Valores en USD al mes, para un entorno.

| Componente | A. AWS (contenedores) | B. AWS (serverless) | C. GCP | D. Azure |
|---|---|---|---|---|
| API y portal | ECS Fargate + ALB | Lambda con Lambda Web Adapter, misma imagen | Cloud Run | Container Apps |
| Tareas | ECS RunTask (Fargate) | ECS RunTask (Fargate) | Cloud Run Jobs | Container Apps jobs |
| PostgreSQL 18 | RDS | RDS | Cloud SQL | Flexible Server |
| Control de acceso sin código | ALB con autenticación OIDC o Cognito | Requiere CloudFront y Lambda@Edge, o un ALB | IAP directo en Cloud Run, sin balanceador | Autenticación integrada de Container Apps |
| Costo base estimado | ~48 | ~12 a 15, sin el control de acceso | ~10 | ~13 a 20 |
| Componentes principales | VPC, subredes, ALB, cluster, servicio, tareas, RDS | VPC, Lambda, URL o API Gateway, tareas, RDS | Servicio, job, Cloud SQL, IAP | Entorno, app, job, Flexible Server, ACR |
| Experiencia del operador | Alta | Alta | Baja | Media |

Supabase como PostgreSQL administrado (sin su API, autenticación ni almacenamiento) no reduce componentes en ninguna alternativa y añade un proveedor. Queda descartado mientras no aparezca una ventaja concreta.

## Evidencia

- Los tres proveedores ofrecen PostgreSQL 18 administrado.
- En AWS, un balanceador y las IPv4 públicas cuestan más que el cómputo y la base juntos con tráfico bajo. La variante sin balanceador (B) traslada esa complejidad al control de acceso.
- Cloud Run admite IAP directamente sobre el servicio, sin balanceador y sin cargo adicional, salvo excepciones documentadas.
- Con pocas ejecuciones dominan las capas gratuitas (GCP y Azure). Con muchas, Fargate tiene el precio unitario más bajo.
- No se ha desplegado nada en ninguna nube: todo lo anterior son precios y documentación, no mediciones.

## Propuesta

**C. GCP**, condicionada a una prueba de concepto en `staging` que cumpla FDH-009-AC-07, AC-08, AC-11 y AC-17:

- Cloud Run para el portal y la API: una unidad con dos contenedores o dos servicios, según el plan de FDH-009.
- Cloud Run Jobs para las tareas.
- Cloud SQL para PostgreSQL 18, sin IP pública abierta.
- Artifact Registry, Secret Manager, Cloud Logging y Cloud Monitoring.
- IAP para el control de acceso.
- Federación de identidad de cargas de trabajo para GitHub Actions.
- OpenTofu con el estado en un bucket de Cloud Storage con versionado.

**Por qué**: satisface los criterios 1, 2 y 3 con el menor número de componentes y el menor costo base. Además, el equipo de ETL ya trabaja con Colab, del mismo ecosistema.

**En contra**: el operador de infraestructura tiene más experiencia en AWS (criterio 7). Si la mantenedora valora más ese criterio, la alternativa preferible es **A (AWS con ECS Fargate y ALB con autenticación OIDC)**: cuesta más, pero tiene menos piezas que inventar que B.

## Consecuencias

- `infra/` contiene la configuración de OpenTofu del proveedor elegido. El código de `backend/src/` no cambia por el proveedor.
- Hay que resolver en el plan de FDH-009 la parametrización de `nginx.conf` y de TLS en la conexión a PostgreSQL ([hallazgos](../../specs/009-cloud-platform/spec.md#impacto-en-el-código-existente)).
- El almacenamiento de objetos de FDH-004 tendrá por defecto el servicio del proveedor elegido. La compatibilidad con S3 y el uso de un emulador local se verifican en esa etapa.
- Cambiar de proveedor después implica reescribir `infra/`, no la aplicación.

## Pendiente

- Aprobación de la mantenedora y respuestas a las preguntas de FDH-009.
- Confirmar los precios secundarios en las calculadoras oficiales.
- Verificar si el SLA del proveedor elegido cubre la instancia de base de datos mínima.
- Prueba de concepto y su evidencia en `research/`.
