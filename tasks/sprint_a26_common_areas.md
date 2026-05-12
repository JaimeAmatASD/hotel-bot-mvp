# Sprint A.2.6 — Zonas comunes como ubicación válida

## Bug descubierto en A.2 (corregido aquí)

`_GENERIC_LOCATION_WORDS` en `config/rules.py` lista "lobby", "pasillo", "piscina",
"recepcion", "jardin" como ubicaciones *genéricas* — exactamente lo contrario de lo que
queremos. Esto hacía que "mancha en el lobby" triggerara un followup innecesario.
El A.2.6 reemplaza esa heurística entera por `is_location_complete()`.

## Plan de implementación

### Paso 1 — `config/rules.py`
- [ ] Añadir constante `COMMON_AREAS` (set de strings ya normalizados, sin tildes)
- [ ] Añadir función `is_location_complete(ubicacion: str | None) -> bool`:
  - `None` o `""` → False
  - Contiene dígito → True (número de habitación)
  - Contiene alguna palabra de `COMMON_AREAS` (split + strip de puntuación) → True
  - Cualquier otra cosa → False
- [ ] Eliminar `_GENERIC_LOCATION_WORDS` y `is_generic_location()` — reemplazadas por
  `is_location_complete()`. Solo se usan en `brain.py`, no hay más referencias.

Nota: `_normalize()` ya existe y sirve para `is_location_complete()`. No tocar.

### Paso 2 — `brain.py`
- [ ] Cambiar import: quitar `is_generic_location`, añadir `is_location_complete`
- [ ] Cambiar condición en `_apply_followup`:
  - Antes: `if tipo == "INCIDENCIA" and (ubicacion is None or is_generic_location(ubicacion)):`
  - Después: `if tipo == "INCIDENCIA" and not is_location_complete(ubicacion):`
  - Quitar la variable `ubicacion` que ya estaba fuera del if (ahora se pasa directo)
- [ ] No tocar nada más en brain.py

### Paso 3 — `tests/test_common_areas.py`
- [ ] 8 tests `is_location_complete == True`: hab 204, hab. 305 baño, Lobby, lobby cerca
  de recepción, alfombra del lobby, ducha del spa, Spa, Piscina exterior
- [ ] 4 tests `is_location_complete == False`: "una habitación", "habitación", "baño", None/""

## Criterio de éxito
- `pytest tests/test_common_areas.py` → 12/12
- `pytest tests/` → 11/11 sin regresión
- 5 casos manuales desde Telegram (con /debug on)

## Para después (no en este sprint)
- "Suite presidencial", "habitación deluxe", nombres propios de habitaciones sin número
  → no se detectan como completas. Añadir a COMMON_AREAS si aparece en piloto.
- Texto compuesto tipo "pasillo del ala este, tercer piso" — funciona porque "pasillo"
  está en COMMON_AREAS. No requiere cambio.
- Si en el hotel piloto hay zonas con nombre propio (ej: "Salón Mediterráneo"), añadir
  al set. Son dos líneas.
