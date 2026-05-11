# Sprint A.1.5 — Fix sesgo de departamento en el clasificador

## Diagnóstico

`classifier.py`, línea 71 (último párrafo de SYSTEM_PROMPT):

```
Recibirás antes del mensaje un bloque con: nombre, departamento
(HOUSEKEEPING, RECEPCION, MANTENIMIENTO, RESTAURANTE, OTRO),
idioma preferido. Úsalo para entender el contexto pero no lo
agregues al output.
```

"Úsalo para entender el contexto" es ambiguo — Gemini lo interpreta como
pista de clasificación. Un empleado del Spa que reporta una bombilla
tiende a recibir categoría SPA en lugar de MANTENIMIENTO.

## Plan de implementación

### Paso 1 — `classifier.py` (único archivo a tocar para el fix)

Reemplazar el bloque `# Contexto del empleado` al final del SYSTEM_PROMPT por:

```
# Importante sobre el departamento del empleado

El departamento del empleado es solo metadato sobre quién reporta.
NO asumas que el mensaje es sobre su departamento. Un empleado del spa
puede reportar problemas de mantenimiento, recepción, jardinería o
cualquier cosa que vea durante su turno. Clasifica EXCLUSIVAMENTE en
base al CONTENIDO del mensaje, no en base al departamento del empleado.
El departamento solo sirve para entender el contexto del lenguaje
(un empleado de cocina puede usar jerga gastronómica) pero NO determina
la categoría.
```

Cambio quirúrgico: solo se toca ese último bloque del string. El resto del
SYSTEM_PROMPT no se modifica.

### Paso 2 — `test_cross_department.py` (nuevo archivo de datos)

Archivo nuevo al mismo nivel que `test_cases.py` y `test_extended.py`.
Mismo formato de lista de dicts, pero con campos adicionales:
- `expected_categoria` — la categoría correcta según el contenido
- `expected_tipo_nota_huesped` — solo en casos GUEST_INTEL que lo requieran

```python
CROSS_TESTS = [5 casos del enunciado]
```

No es un archivo pytest — es un archivo de datos que importa `evaluate.py`.

### Paso 3 — `evaluate.py`

Agregar función `run_cross_suite(cases, label)` que extiende `run_suite()`:
- Chequea `tipo` (igual que antes)
- Chequea `categoria` si el caso tiene `expected_categoria`
- Chequea `tipo_nota_huesped` si el caso tiene `expected_tipo_nota_huesped`
- Un caso pasa solo si TODOS los campos chequeados son correctos

Agregar opción `"cross"` en `main()` (análogo a `"core"` y `"extended"`).

```
python3 evaluate.py cross    # solo los 5 cross tests
python3 evaluate.py all      # core + extended + cross (regresión completa)
```

## Criterio de éxito

1. `python3 evaluate.py cross` → 5/5 pasan.
2. `python3 evaluate.py all` → core ≥85%, extended ≥80% (igual o mejor que antes del cambio).

## Para después (no en este sprint)

- Los departamentos en el prompt del usuario son "Spa", "RECEPCION", etc. — hay inconsistencia de capitalización entre los datos reales y el schema del SYSTEM_PROMPT. No tocar ahora.
- CROSS-03 (Andrei de Mantenimiento captura GUEST_INTEL) podría agregar `expected_tipo_nota_huesped: "ALERGIA"` — incluido en el test según el enunciado.
