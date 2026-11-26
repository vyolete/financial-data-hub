# FDH-009 — Plataforma de despliegue en la nube

**Estado**: Draft (propuesta; sin registro de aprobación)
**Issue de seguimiento**: pendiente de crear
**Base**: `feature/fdh-001-discovery-catalog` @ `60d84f4`
**Decisión relacionada**: [ADR-0009](../../docs/adr/0009-cloud-platform.md) (Proposed)
**Evidencia**: [costos y capacidades de nube](../../research/benchmarks/cloud-platform-costs/README.md)

## Contexto

FDH-001 se ejecuta solo en local, y su especificación deja fuera el «despliegue productivo». El roadmap no tiene una etapa de despliegue: FDH-008 cubre objetivos de servicio y recuperación cuando ya existe algo desplegado.

Los artefactos ya existen y no cambian de comportamiento:

- una imagen de backend que sirve la API y ejecuta la CLI (`fdh`, `alembic`);
- una imagen del portal (nginx con el build de React);
- PostgreSQL 18 y migraciones Alembic;
- `config/sources.toml`, versionado y sin secretos.

Esta especificación define cómo ejecutar esos artefactos en un entorno de nube reproducible, seguro y con costo acotado. No añade funcionalidad de producto.

## Preguntas para aclarar

Cada pregunta trae una respuesta propuesta. Ninguna está decidida.

1. [NEEDS CLARIFICATION] ¿Qué proveedor de nube? → Propuesta: ver [ADR-0009](../../docs/adr/0009-cloud-platform.md).
2. [NEEDS CLARIFICATION] ¿El entorno es privado o público? FDH-001 establece que ningún servicio sin autenticación se expone públicamente, y la API y el portal no tienen autenticación. → Propuesta: privado, con acceso solo a identidades autorizadas mediante el proxy de identidad del proveedor. La apertura pública requiere una especificación de autenticación aparte.
3. [NEEDS CLARIFICATION] ¿Cuántos entornos? → Propuesta: uno (`staging`) en esta etapa; `production` cuando exista una versión `Released` y una necesidad aprobada.
4. [NEEDS CLARIFICATION] ¿Cuál es el presupuesto mensual? Hay 6 millones de COP asignados a infraestructura para iniciar, sin precisar si son mensuales o totales. → Propuesta: tope de alerta de 50 USD al mes para `staging`.
5. [NEEDS CLARIFICATION] ¿Terraform u OpenTofu? → Propuesta: OpenTofu, por licencia abierta (MPL-2.0) en un repositorio Apache-2.0 y compatibilidad con los proveedores de Terraform. La sintaxis HCL no impide cambiar después.
6. [NEEDS CLARIFICATION] ¿Qué región? → Propuesta: una región de EE. UU. con PostgreSQL 18 administrado y el precio más bajo. Si se exige residencia en Colombia o latencia mínima desde allí, la elección cambia.
7. [NEEDS CLARIFICATION] ¿El descubrimiento en la nube es programado? → Propuesta: no. Bajo demanda, lanzado desde GitHub Actions. La programación es FDH-005.
8. [NEEDS CLARIFICATION] ¿El producto es comercial? El repositorio lo presenta como proyecto público para analistas, docentes y estudiantes. → Afecta las condiciones de uso de fuentes como FRED y los entornos necesarios. Lo decide la mantenedora.

## Escenarios de usuario

- **P1 — Despliegue**: una persona operadora fusiona un cambio aprobado. GitHub Actions construye las imágenes, aplica migraciones y despliega en `staging`. La persona ve en el portal la versión desplegada.
- **P1 — Descubrimiento bajo demanda**: una persona operadora lanza `fdh discover --source <id>` contra `staging` desde GitHub Actions y ve la ejecución, exitosa, parcial o fallida, en el portal.
- **P2 — Recreación**: una persona de infraestructura destruye `staging` y lo recrea desde un clon limpio con los comandos documentados.
- **P2 — Recuperación**: tras perder la base de datos, una persona la restaura desde un respaldo dentro del objetivo de recuperación.
- **P3 — Costo**: la mantenedora recibe una alerta cuando el gasto del mes alcanza los umbrales del presupuesto.

## Conceptos

| Concepto | Código | Definición |
|---|---|---|
| Entorno | `environment` | Conjunto aislado de recursos de nube con nombre estable (`staging`, `production`) |
| Bootstrap | `bootstrap` | Recursos mínimos creados una vez, fuera del ciclo normal: cuenta o proyecto, backend de estado de IaC y federación de identidad para GitHub Actions |
| Tarea operativa | `job` | Ejecución finita de un comando de la imagen de backend (`alembic upgrade head`, `fdh config check`, `fdh sources sync`, `fdh discover`) |
| Versión desplegada | `release` | Par de imágenes identificadas por digest y construidas desde un commit |

## Requisitos

- **FDH-009-FR-01**: Todo recurso de nube se declara en código versionado bajo `infra/`. Solo el bootstrap puede crearse fuera de ese ciclo, y queda documentado paso a paso. Un cambio de infraestructura muestra su plan en el PR antes de aplicarse.
- **FDH-009-FR-02**: GitHub Actions construye las imágenes existentes (`backend/Dockerfile`, `frontend/Dockerfile`), las etiqueta con el SHA del commit y las publica en un registro privado. El despliegue referencia cada imagen por digest. La imagen que se prueba es la que se despliega.
- **FDH-009-FR-03**: PostgreSQL administrado con la misma versión mayor que el entorno local (18). La base no tiene acceso público: se llega por red privada o por un conector autenticado y cifrado del proveedor.
- **FDH-009-FR-04**: Antes de activar una versión nueva de la API, una tarea ejecuta `alembic upgrade head`. Si falla, la versión anterior sigue activa y el despliegue se informa como fallido.
- **FDH-009-FR-05**: La API se ejecuta desde la imagen de backend sin cambios de comportamiento y expone `/health` como comprobación de salud.
- **FDH-009-FR-06**: El portal se ejecuta desde la imagen del portal y llega a la API solo por la ruta HTTP documentada (`/api/`), como en local.
- **FDH-009-FR-07**: Las tareas operativas usan la misma imagen de backend, se lanzan bajo demanda desde GitHub Actions y registran quién las lanzó y con qué parámetros. No hay ejecuciones programadas.
- **FDH-009-FR-08**: La configuración de fuentes usada en la nube es `config/sources.toml` del commit desplegado, de solo lectura y sin edición manual en la consola.
- **FDH-009-FR-09**: La contraseña de la base de datos y los tokens opcionales de fuentes (`FDH_SOCRATA_APP_TOKEN`) viven en el gestor de secretos del proveedor y llegan al contenedor como variables de entorno. GitHub Actions se autentica en la nube por federación OIDC, sin claves de larga duración.
- **FDH-009-FR-10**: Mientras no exista una especificación de autenticación aprobada, la API y el portal solo son accesibles para identidades autorizadas, mediante un control de acceso del proveedor que no requiere cambios en el código.
- **FDH-009-FR-11**: Volver a la versión anterior consiste en desplegar de nuevo el par de digests anterior, sin reconstruir imágenes.
- **FDH-009-NFR-01**: Costo. Existe un presupuesto con alertas al 50, 80 y 100 % del tope aprobado. Cada recurso lleva las etiquetas `project`, `environment` y `managed-by`. El PR que crea o cambia recursos incluye la estimación del costo mensual.
- **FDH-009-NFR-02**: Seguridad.
  - Cada componente (API, portal, tareas, despliegue) usa su propia identidad, con permisos mínimos.
  - Cifrado en reposo y en tránsito.
  - Registro privado y base de datos sin acceso público.
  - Los contenedores conservan usuario no root y sistema de archivos de solo lectura, como en Compose.
  - El estado de IaC se guarda cifrado, con versionado y acceso restringido, y nunca en el repositorio.
- **FDH-009-NFR-03**: Observabilidad. Los logs JSON de API, portal y tareas se centralizan, con retención acotada. Un fallo de la comprobación de salud o de una tarea genera una alerta.
- **FDH-009-NFR-04**: Recuperación. Respaldos automáticos diarios de la base, con retención mínima y recuperación a un punto en el tiempo si el servicio la ofrece. La restauración se prueba y se documenta antes de pasar a `Verified`.
- **FDH-009-NFR-05**: Reproducibilidad. Desde un clon limpio, los comandos documentados crean, actualizan y destruyen `staging`. El entorno local sigue funcionando con Docker Compose sin servicios de pago (constitución VI).
- **FDH-009-NFR-06**: Portabilidad. El código de `backend/src/` no importa SDK de ningún proveedor de nube. Las diferencias entre local y nube se resuelven con variables de entorno y en `infra/`.

## Límites y valores propuestos

| Límite | Valor propuesto |
|---|---|
| Instancias mínimas de la API y del portal | 0 (escala a cero) |
| Instancias máximas de la API y del portal | 2 |
| Tiempo máximo de una tarea operativa | 30 min |
| Retención de logs | 30 días |
| Retención de respaldos de la base | 7 días |
| RPO / RTO de `staging` | 24 h / 4 h |
| Tope de alerta de presupuesto de `staging` | 50 USD al mes |

## Impacto en el código existente

Hallazgos de la revisión de `60d84f4`. El plan decide cómo resolverlos; ninguno cambia requisitos de FDH-001.

1. `frontend/nginx.conf` acepta solo `server_name localhost 127.0.0.1`, responde 444 a cualquier otro host y usa `proxy_pass http://api:8000` fijo. En la nube hay que parametrizar el host y la dirección de la API, por ejemplo con plantillas y variables de entorno.
2. `backend/src/fdh/persistence/session.py` no fija TLS en la conexión a PostgreSQL. Hace falta un parámetro de entorno para exigirlo, o para usar el socket del conector del proveedor.
3. `FDH_API_ALLOWED_HOSTS` debe incluir el nombre de host del entorno. Ya es configurable.
4. El `Dockerfile` del backend espera `config/sources.toml` montado en tiempo de ejecución. El plan elige cómo llevarlo a la nube (volumen de configuración, montaje de secreto o imagen derivada) sin perder FR-08.

## Criterios de aceptación

| ID | Requisitos | Criterio |
|---|---|---|
| FDH-009-AC-01 | FR-01 | Ningún recurso de `staging` fuera del bootstrap documentado existe sin estar en `infra/`; la detección de deriva (`plan` sin cambios) pasa tras cada `apply` |
| FDH-009-AC-02 | FR-01 | Un PR que modifica `infra/` publica el plan de cambios antes de aplicarse; aplicar requiere aprobación humana en un entorno protegido de GitHub |
| FDH-009-AC-03 | FR-02 | La imagen desplegada tiene el mismo digest que la imagen construida y probada en el pipeline, y su etiqueta es el SHA del commit |
| FDH-009-AC-04 | FR-03, NFR-02 | La base de datos no acepta conexiones desde internet; una conexión sin TLS o sin credencial válida se rechaza |
| FDH-009-AC-05 | FR-03 | La versión mayor de PostgreSQL en `staging` es 18 |
| FDH-009-AC-06 | FR-04 | Si una migración falla, la API sigue sirviendo la versión anterior y el workflow termina en error visible |
| FDH-009-AC-07 | FR-05, FR-06 | Con un usuario autorizado, `/health` responde correctamente y el portal muestra los mismos registros que la API |
| FDH-009-AC-08 | FR-07 | `fdh discover --source co-datos-gov` lanzado desde GitHub Actions deja una ejecución visible en el portal con su estado real, y el workflow registra quién la lanzó y con qué parámetros |
| FDH-009-AC-09 | FR-08 | Cambiar `config/sources.toml` sin desplegar no cambia la configuración en `staging`; tras desplegar, la tarea `fdh config check` valida la versión del commit desplegado |
| FDH-009-AC-10 | FR-09 | Ni el repositorio, ni los logs, ni el estado de IaC en texto plano contienen la contraseña de la base ni tokens; el workflow no usa claves de nube de larga duración |
| FDH-009-AC-11 | FR-10 | Una solicitud sin identidad autorizada a la API o al portal recibe una denegación antes de llegar al contenedor |
| FDH-009-AC-12 | FR-11 | Desplegar el par de digests anterior restaura la versión previa sin reconstruir imágenes |
| FDH-009-AC-13 | NFR-01 | Existen alertas de presupuesto al 50, 80 y 100 %, y todos los recursos de `staging` tienen las etiquetas requeridas |
| FDH-009-AC-14 | NFR-02 | Cada identidad de ejecución tiene solo los permisos de su función; la de la API no puede lanzar tareas ni leer secretos ajenos |
| FDH-009-AC-15 | NFR-03 | Los logs de una ejecución de descubrimiento pueden consultarse centralizados por su identificador de ejecución; detener la API dispara una alerta |
| FDH-009-AC-16 | NFR-04 | Existe evidencia en `research/` de una restauración de respaldo con fecha UTC, duración y datos verificados |
| FDH-009-AC-17 | NFR-05 | Destruir y recrear `staging` desde un clon limpio con los comandos documentados produce un entorno que cumple AC-07; `docker compose up` sigue funcionando sin credenciales de nube |
| FDH-009-AC-18 | NFR-06 | Una prueba de arquitectura comprueba que `backend/src/` no importa SDK de nube |

## Fuera de alcance

- Almacenamiento de objetos y capas Bronze, Silver y Gold (FDH-004). Su producto se decide con un ADR propio.
- Orquestación y ejecuciones programadas, incluido Dagster (FDH-005).
- Autenticación de usuarios finales y acceso público.
- Alta disponibilidad multizona, múltiples regiones y entorno `production`.
- Dominio propio y certificados personalizados, salvo que se aclare lo contrario.
- Integración de Lovable.

## Riesgos

- Si el entorno se abre al público antes de tener autenticación, se incumple una aclaración aprobada de FDH-001.
- Una base de datos compartida o burstable mínima puede limitar el rendimiento. Es aceptable en `staging`, no necesariamente en `production`.
- El estado de IaC puede contener valores sensibles generados. Se mitiga con contraseñas administradas por el servicio cuando existan y con un backend de estado cifrado y restringido.
- El ritmo de cambios del proyecto puede dejar decisiones de infraestructura implícitas si esta especificación no se aprueba antes que FDH-003.

## Puntos abiertos para el plan

1. ¿El portal y la API se despliegan como una unidad con dos contenedores (nginx delante, API en `127.0.0.1`), o como dos servicios?
2. ¿Cómo se monta `config/sources.toml`?
3. ¿Cómo se ejecutan las migraciones respecto al despliegue: tarea previa o paso del workflow?
4. ¿Dónde viven los workflows de infraestructura y con qué protección de entornos de GitHub?
5. ¿Cómo se organiza el directorio `infra/`: módulos, entornos y backend de estado?
