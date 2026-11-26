# ADR-0007: Integración y orquestación de referencia

- **Fecha**: 2026-11-25
- **Estado**: Accepted como referencia; selección definitiva condicionada a pruebas de concepto
  (registro verificable en GitHub pendiente)
- **Autoridad**: aprobada por la mantenedora en sesión de trabajo del 2026-11-25. El registro
  verificable es un comentario personal suyo en el
  [issue #2](https://github.com/vyolete/financial-data-hub/issues/2); aún no consta.
- **Sustituye**: el párrafo sobre dlt y Dagster de [ADR-0003](0003-technology-stack.md).

## Contexto

No conviene desarrollar desde cero capacidades que puedan reutilizarse justificadamente.

## Alternativas a comparar

| Opción | Integración | Orquestación |
|---|---|---|
| A (referencia) | dlt | Dagster |
| B | Airbyte | Dagster |
| C | Meltano | Por elegir |
| D | Motor especializado en Python | Por elegir |

## Evidencia

Ninguna todavía: no se ha instalado ni probado ninguna opción.

## Decisión

Tomar dlt como motor de integración de referencia y Dagster como orquestador de referencia,
conservando la comparación. Airflow no está entre las opciones aprobadas.

## Condiciones para confirmar

Pruebas de concepto sobre los mismos casos y un ADR con sus resultados. Criterios **propuestos**,
a fijar en FDH-002 y FDH-003: ajuste a los contratos, carga incremental y estado, manejo de
errores y reintentos, consumo de recursos, operación local, pruebas, licencia y esfuerzo de
mantenimiento.

## Consecuencias

- No se instalan en FDH-001.
- Los contratos propios no dependen de ninguna de estas herramientas.
