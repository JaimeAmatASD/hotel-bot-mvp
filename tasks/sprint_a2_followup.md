# Sprint A.2 — Bot pide info crítica faltante

## Decisión de diseño: estados separados vs unificados

**Decisión: mantener `awaiting_correction` y `awaiting_followup` como flags separadas.**

Por qué no fusionar:
- Fusionar requeriría refactorizar el código del A.1 que ya funciona y está testeado.
- Los triggers son distintos: `awaiting_correction` lo inicia el usuario (pulsa "Corregir");
  `awaiting_followup` lo inicia el bot (detecta campo faltante).
- En los handlers, `awaiting_followup` tiene **prioridad más alta** — el bot hizo una pregunta
  concreta y espera su respuesta. Si hay ambas activas a la vez (no debería pasar, pero sí),
  seguir con la del bot es más correcto.
- El mecanismo de `previous_context` y timeout es idéntico en ambos casos → se puede reutilizar
  el mismo patrón sin necesitar el mismo flag.

## Flujo completo (post-A.2)

```
Mensaje del empleado
  │
  ├─ awaiting_followup? ──→ procesar como respuesta al followup
  │    └─ timeout? → avisar, ir a normal
  │
  ├─ awaiting_correction? ──→ procesar como corrección (A.1)
  │    └─ timeout? → avisar, ir a normal
  │
  └─ Normal
       │
       └─ process_message(input, employee)
            │
            ├─ confianza < 0.6 → pedir reformular (sin botones)
            ├─ 0.6 ≤ conf < 0.8 → mostrar resumen + aviso ⚠️ + botones normales
            └─ conf ≥ 0.8
                 ├─ needs_followup → mostrar pregunta, guardar awaiting_followup
                 └─ sin followup → resumen normal + botones
```

## Plan de implementación

### Paso 1 — `config/rules.py` (nuevo)
- [ ] Constante `CRITICAL_MISSING_FIELDS` dict por tipo
- [ ] Constante `MISSING_FIELD_QUESTIONS` dict
- [ ] Función `get_critical_field(tipo, campos_faltantes) -> str | None`
  - Normaliza tildes en los campos (unicodedata.normalize + lower)
  - Devuelve el primer campo de `campos_faltantes` que matchea la lista crítica del tipo
  - Devuelve `None` si ninguno es crítico
- [ ] Función `is_generic_location(ubicacion: str | None) -> bool`
  - Devuelve True si `ubicacion` no contiene ningún dígito Y coincide con palabras genéricas
    (habitación, baño, cuarto, zona, área, pasillo, lobby — sin número de room)
  - Usa regex simple: `not re.search(r'\d', ubicacion)` + palabras conocidas

### Paso 2 — `brain.py`
- [ ] Importar las funciones de `config.rules`
- [ ] Después del `classify()`, antes del return:
  1. Si `tipo == "INCIDENCIA"` y `ubicacion` es genérica → añadir `"ubicacion"` a `campos_faltantes`
     (solo si no está ya)
  2. Llamar `get_critical_field(tipo, campos_faltantes)` → si hay campo crítico, añadir al result:
     ```python
     result["needs_followup"] = {
         "field": campo_critico,
         "question": MISSING_FIELD_QUESTIONS.get(campo_critico, f"Necesito un dato más: ¿{campo_critico}?")
     }
     ```
  3. Si no hay campo crítico, no añadir `needs_followup` (el handler usa `.get()`)

### Paso 3 — `handlers/__init__.py`
- [ ] Añadir función `format_summary_with_warning(result) -> str`
  - Llama a `format_summary(result)` y agrega línea `⚠️ <i>Tengo dudas sobre la clasificación, confirmá si está bien.</i>`

### Paso 4 — `handlers/text_handler.py`
- [ ] Añadir `_pop_followup_state(context)` → mismo patrón que `_pop_correction_state`:
  - Chequea `awaiting_followup`
  - Limpia `awaiting_followup` + `followup_started_at` + `pending`
  - Retorna `(previous_pending, timed_out)`
- [ ] En `handle_text`, reordenar la detección de estado al inicio:
  ```
  1. previous_context, timed_out = _pop_followup_state(context)
  2. Si no había followup: previous_context, timed_out = _pop_correction_state(context)
  ```
  En ambos casos si timed_out, avisar y continuar sin previous_context.
- [ ] Después de `process_message`:
  - Si `confianza < 0.6` → responder con mensaje de reformular, return (sin guardar pending)
  - Si `0.6 ≤ confianza < 0.8` → usar `format_summary_with_warning`, botones normales
  - Si `confianza ≥ 0.8` y `needs_followup` → preguntar, guardar `awaiting_followup=True` +
    `followup_started_at` + `pending`, return
  - Si `confianza ≥ 0.8` y sin followup → flujo normal

### Paso 5 — `handlers/audio_handler.py`
- [ ] Mismo cambio que text_handler (estado + thresholds de confianza + needs_followup)

### Paso 6 — `tests/test_followup_flow.py`
- [ ] **Test 1 — incidencia sin habitación pide habitación:**
  mock de process_message devuelve resultado con `needs_followup={"field": "habitacion", "question": "¿En qué habitación?"}` → verificar que el bot pregunta por habitación y guarda `awaiting_followup=True`
- [ ] **Test 2 — respuesta al followup combina contextos:**
  estado previo con `awaiting_followup=True` + pending del mensaje original → usuario responde "412" → verificar que `process_message` recibe `previous_context` con el pending original
- [ ] **Test 3 — confianza baja pide reformular:**
  mock devuelve `{"tipo": "INCIDENCIA", ..., "confianza": 0.4}` → verificar que el bot no guarda pending y envía mensaje de reformular
- [ ] **Test 4 — confianza media muestra aviso pero no bloquea:**
  mock devuelve resultado con `confianza=0.7` sin `needs_followup` → verificar que el resumen contiene "⚠️" Y se manda el `CONFIRM_KEYBOARD`

## Notas de implementación

- El timeout para `awaiting_followup` reutiliza `CORRECTION_TIMEOUT_MINUTES = 5` pero con
  flag separada `followup_started_at`. No importar la constante entre handlers — cada handler
  la define o la saca de un lugar compartido. Para evitar DRY, moverla a `config/rules.py`.
- El mensaje de reformular: *"No entendí bien tu mensaje. ¿Podés contarme de nuevo qué pasó?"*
- El campo `needs_followup` no se guarda en el `pending` — es solo para que el handler lo lea
  y decida qué mostrar. El `pending` sigue siendo `{"result": result, "original_text": text}`.

## Criterio de éxito

- `pytest tests/test_followup_flow.py` → 4/4 pasan
- Test manual: 4 casos descritos en el enunciado desde Telegram real

## Para después (no en este sprint)

- Actualmente se pregunta solo por el campo MÁS crítico (el primero de la lista). Si hay dos
  campos críticos faltantes (habitación Y ubicación), se hace una sola pregunta. Para preguntas
  encadenadas (wizard multi-step), ver Sprint A.4 si se decide hacer.
- El aviso de confianza media es genérico ("tengo dudas sobre la clasificación"). Podría
  ser más específico señalando el campo dudoso. Mejora para Sprint A.4.
- Si el empleado responde a un followup con algo que no es el dato pedido (ej: dice "ok" en vez
  de un número de habitación), el clasificador reprocesa igualmente. No hay validación de que la
  respuesta sea útil. Mejorar si se observa en producción.
