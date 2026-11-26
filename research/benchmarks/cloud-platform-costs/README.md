# Costos y capacidades de nube para el despliegue (FDH-009)

**Objetivo**: aportar evidencia de precios y capacidades para [ADR-0009](../../../docs/adr/0009-cloud-platform.md) y la especificación [FDH-009](../../../specs/009-cloud-platform/spec.md).
**Fecha de consulta**: 2026-11-26 (UTC).
**Método**: lectura de páginas de precios y documentación. No se creó ningún recurso ni se ejecutó ninguna prueba en una nube.

## Limitaciones

- Son precios de lista, sin impuestos, descuentos, créditos ni compromisos, en regiones de EE. UU. (`us-east-1`, `us-central1`, `eastus`).
- Algunas tablas oficiales no muestran el precio sin iniciar sesión o sin JavaScript. En esos casos se usó una fuente secundaria y se marca como tal. Antes de aprobar el ADR, confirmar cada valor con la calculadora oficial de cada proveedor.
- Los escenarios de uso son supuestos, no mediciones: el proyecto no tiene volumen definido.
- Los totales se calcularon con aritmética simple (Python) sobre los valores de esta página.

## Precios unitarios

| Concepto | Valor | Fuente | Tipo |
|---|---|---|---|
| AWS Fargate Linux/x86, us-east-1 | 0,000011244 USD por vCPU-segundo; 0,000001235 USD por GB-segundo | <https://aws.amazon.com/fargate/pricing/> | Oficial |
| AWS Fargate Linux/ARM, us-east-1 | 0,0000089944 USD por vCPU-segundo; 0,0000009889 USD por GB-segundo | <https://aws.amazon.com/fargate/pricing/> | Oficial |
| AWS NAT Gateway | 0,045 USD por hora más 0,045 USD por GB procesado | <https://aws.amazon.com/vpc/pricing/> | Oficial |
| AWS IPv4 pública | 0,005 USD por IP y hora | <https://aws.amazon.com/blogs/aws/new-aws-public-ipv4-address-charge-public-ip-insights/> | Oficial |
| AWS Application Load Balancer | 0,0225 USD por hora más LCU | <https://aws.amazon.com/elasticloadbalancing/pricing/> | Oficial |
| AWS Secrets Manager | 0,40 USD por secreto y mes; 0,05 USD por 10.000 llamadas | <https://aws.amazon.com/secrets-manager/pricing/> | Oficial |
| Amazon RDS PostgreSQL `db.t4g.micro`, Single-AZ | ~0,016 USD por hora (~12 USD al mes) | <https://sparecores.com/database/aws/db.t4g.micro>, <https://www.bytebase.com/dbcost/rds/instance/db.t4g.micro/> | Secundaria |
| Amazon S3 Standard | 0,023 USD por GB y mes (primeros 50 TB) | <https://www.cloudzero.com/blog/s3-pricing> | Secundaria |
| Cloud Run (instancia) | 0,000018 USD por vCPU-segundo; 0,000002 USD por GiB-segundo | <https://cloud.google.com/run/pricing> | Oficial |
| Cloud Run Jobs, capa gratuita | 240.000 vCPU-segundos y 450.000 GiB-segundos al mes | <https://cloud.google.com/run/pricing> | Oficial |
| Cloud SQL PostgreSQL, instancia de prueba (1 CPU compartida, 0,6 GB, 10 GB, sin HA ni respaldos) | 9,37 USD al mes en `us-central1` | <https://cloud.google.com/sql/docs/postgres/pricing-examples> | Oficial |
| Cloud Storage Standard, `us-central1` | 0,020 USD por GB y mes | <https://cloud.google.com/storage/pricing> | Oficial |
| Secret Manager (Google) | 0,06 USD por versión activa y ubicación; 6 versiones gratis | <https://cloud.google.com/secret-manager/pricing> | Oficial |
| IAP en Cloud Run | Activación directa sin balanceador; sin cargo salvo excepciones | <https://cloud.google.com/blog/products/serverless/iap-integration-with-cloud-run> | Oficial |
| Azure Container Apps (consumo), capa gratuita | 180.000 vCPU-segundos, 360.000 GiB-segundos y 2 millones de solicitudes al mes por suscripción | <https://learn.microsoft.com/azure/container-apps/billing> | Oficial |
| Azure Container Apps, uso activo | 0,000024 USD por vCPU-segundo (Central US, 2025) | <https://techcommunity.microsoft.com/blog/appsonazureblog/understanding-idle-usage-in-azure-container-apps/4419197> | Blog de Microsoft; la tabla oficial no cargó |
| Azure PostgreSQL Flexible Server `B1ms` | ~12 USD al mes (US East) | <https://www.bytebase.com/dbcost/azure-flexible/instance/B1ms/> | Secundaria |
| Azure Blob Hot LRS | ~0,018 USD por GB y mes (East US) | <https://www.opslyft.com/blog/azure-blob-storage-pricing> | Secundaria |

## Compatibilidad con PostgreSQL 18

El entorno local usa la imagen `postgres:18` ([compose.yaml](../../../compose.yaml)).

| Servicio | Situación | Fuente |
|---|---|---|
| Amazon RDS | Soporta la versión mayor 18 desde el 2025-11-14 | <https://aws.amazon.com/about-aws/whats-new/2025/11/amazon-rds-postgresql-major-version-18> |
| Cloud SQL | PostgreSQL 18 es la versión predeterminada; la bitácora de mantenimiento llega a 18.6 en 2026 | <https://cloud.google.com/sql/docs/postgres/db-versions>, <https://cloud.google.com/sql/docs/postgres/maintenance-changelog/postgres-18> |
| Azure Flexible Server | PostgreSQL 18 disponible, con extensiones y opciones de E/S limitadas | <https://learn.microsoft.com/azure/postgresql/flexible-server/concepts-supported-versions> |

## Costo base mensual de un entorno (supuesto)

Un entorno con la API disponible, tráfico bajo y la base de datos más pequeña. No incluye almacenamiento de la base de datos, logs, registro de imágenes ni egress.

| Opción | Componentes | Estimación (USD al mes) |
|---|---|---|
| AWS con ECS Fargate y ALB | API Fargate 0,25 vCPU y 0,5 GB siempre encendida (9,01) + ALB (16,43) + 3 IPv4 públicas (10,95) + RDS `db.t4g.micro` (11,68) | ~48 |
| AWS con Lambda | API en Lambda con Lambda Web Adapter (casi 0 con tráfico bajo) + RDS (11,68); tareas en Fargate con IPv4 pública | ~12 a 15, sin incluir el control de acceso |
| GCP | Cloud Run con escala a cero (dentro de la capa gratuita) + Cloud Run Jobs + Cloud SQL de prueba (9,37) + IAP | ~10 |
| Azure | Container Apps con escala a cero (dentro de la capa gratuita) + Flexible Server `B1ms` (~12) + registro de contenedores | ~13 a 20 |

## Tareas de descubrimiento (supuesto)

30 ejecuciones al día de 5 minutos, con 1 vCPU y 2 GiB (escenario S), y diez veces más (escenario M).

| Escenario | AWS Fargate x86 | Cloud Run Jobs | Container Apps jobs |
|---|---|---|---|
| S: 270.000 vCPU-s y 540.000 GiB-s | 3,70 | 0,72 | 2,70 |
| M: 2,7 M vCPU-s y 5,4 M GiB-s | 37,03 | 54,18 | 75,60 |

Con poco volumen dominan las capas gratuitas; al crecer, Fargate tiene el precio unitario más bajo (ARM, ~20 % menos).

## Capacidades relevantes

- **Lambda Web Adapter** ejecuta una aplicación web sin cambios en Lambda, Fargate o local, con la misma imagen y un binario añadido en `/opt/extensions` (<https://aws.github.io/aws-lambda-web-adapter>).
- **Cloud Run Jobs**: tiempo máximo por tarea configurable hasta 168 horas (<https://cloud.google.com/run/docs/configuring/task-timeout>).
- **IAP en Cloud Run**: protege también la URL `run.app` sin balanceador (<https://cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run>).

## Conclusiones

- **Hecho**: los tres proveedores ofrecen PostgreSQL 18 administrado y ejecución de la misma imagen como servicio y como tarea.
- **Hecho**: en AWS, un balanceador y las IPv4 públicas cuestan más que el resto de la plataforma con tráfico bajo.
- **Hipótesis**: con tráfico bajo y acceso restringido, GCP tiene el costo base más bajo y la menor cantidad de componentes. Falta validarlo con un despliegue de prueba.
- **Pendiente**: confirmar los valores secundarios en las calculadoras oficiales.
