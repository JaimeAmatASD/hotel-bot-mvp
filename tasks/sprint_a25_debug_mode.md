# Sprint A.2.5 — Modo debug activable por comando

## Decisión de diseño: separar format_debug_block vs función unificada

**Decisión: `format_debug_block(result)` separado, concatenado en el handler.**

Por qué no una función unificada `format_summary_with_debug(result, debug_mode)`:
- Mezclaría responsabilidades: el formato del resumen y la decisión de mostrar debug son capas distintas.
- Ya tenemos `format_summary` y `format_summary_with_warning` — añadir otro parámetro bool
  a todas las firmas o crear una función dios para todas las combinaciones es sobreingeniería.
- El handler ya hace la decisión de qué summary mostrar (normal vs warning). Añadir el debug
  ahí mismo es natural: `if debug_mode: summary += "\n" + format_debug_block(result)`.

El handler queda:
```python
debug_mode = get_debug_mode(update.effective_user.id)
summary = format_summary_with_warning(result) if confianza < 0.8 else format_summary(result)
if debug_mode:
    summary += "\n" + format_debug_block(result)
```

## Plan de implementación

### Paso 1 — `storage.py`
- [ ] Añadir creación de tabla `user_preferences` en `init_db()`:
  ```sql
  CREATE TABLE IF NOT EXISTS user_preferences (
      telegram_id INTEGER PRIMARY KEY,
      debug_mode  INTEGER DEFAULT 0
  )
  ```
- [ ] `get_debug_mode(telegram_id: int) -> bool` — SELECT con fallback a False si no existe fila
- [ ] `set_debug_mode(telegram_id: int, enabled: bool)` — INSERT OR REPLACE

### Paso 2 — `handlers/__init__.py`
- [ ] `format_debug_block(result: dict) -> str` — genera el bloque técnico:
  ```
  ─────────────
  🔍 Detalles técnicos:
  • Confianza: 92%
  • Idioma original: es
  • Huésped afectado: sí          (solo si no es null)
  • Habitación huésped: 305       (solo si no es null)
  • Tipo nota huésped: ALERGIA    (solo si no es null)
  • Subcategoría: Sanitarios      (solo si no es null)
  • Campos faltantes: ninguno / lista separada por coma
  ```
  Reglas: campos null no se muestran, excepción `campos_faltantes` que muestra "ninguno".

### Paso 3 — `handlers/command_handler.py` (nuevo)
- [ ] `handle_debug(update, context)`:
  - `/debug on` → `set_debug_mode(tid, True)` + confirma
  - `/debug off` → `set_debug_mode(tid, False)` + confirma
  - `/debug` (sin arg) → muestra estado actual + cómo cambiarlo
  - Cualquier arg no reconocido → igual que sin arg

### Paso 4 — `bot.py`
- [ ] Importar `CommandHandler` de `telegram.ext`
- [ ] Importar `handle_debug` de `handlers.command_handler`
- [ ] `app.add_handler(CommandHandler("debug", handle_debug))`

### Paso 5 — `handlers/text_handler.py`
- [ ] Importar `get_debug_mode` de `storage`
- [ ] Al inicio de `handle_text`: `debug_mode = get_debug_mode(update.effective_user.id)`
- [ ] En el único lugar donde se envía el resumen final: añadir bloque debug si `debug_mode`
  (cubre automáticamente corrección, followup y mensaje inicial — todos pasan por el mismo código)

### Paso 6 — `handlers/audio_handler.py`
- [ ] Mismo cambio que text_handler: `get_debug_mode` al inicio, debug block en el reply final

### Paso 7 — `tests/test_debug_mode.py`
- [ ] **Test 1 (default off)**: mock `get_debug_mode` devuelve False → reply sin bloque debug
- [ ] **Test 2 (toggle on)**: mock `get_debug_mode` devuelve True → reply contiene "🔍 Detalles"
- [ ] **Test 3 (toggle off)**: `set_debug_mode` luego `get_debug_mode` → persiste en SQLite
  (este test usa SQLite real en memoria, no mock)
- [ ] **Test 4 (aislamiento)**: user A tiene debug True, user B tiene debug False →
  handler de B no ve bloque debug

## Notas

- `get_debug_mode` llama `init_db()` internamente (igual que `save`). No hay riesgo de tabla faltante.
- El bloque debug usa `─────────────` como separador visual (no HR de HTML — Telegram lo ignoraría).
- En audio_handler hay un caso especial: cuando `needs_followup`, el bot manda DOS mensajes
  (transcripción + pregunta). El bloque debug no aparece ahí — no hay resumen que enriquecer.
  Solo aparece en el resultado final después de que el usuario responde.

## Criterio de éxito

- `pytest tests/test_debug_mode.py` → 4/4 pasan
- 8 pasos manuales desde Telegram

## Para después (no en este sprint)

- `/debug` podría aceptar `/debug status` más explícito — por ahora sin arg basta.
- El bloque debug en audio podría mostrar también duración del audio y idioma detectado.
  Útil para afinar el transcriptor. Sprint futuro.
- Si se añaden más preferencias de usuario (idioma de respuesta, nivel de detalle),
  `user_preferences` ya tiene la tabla lista — agregar columnas ahí.
