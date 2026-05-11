# Sprint A.1 — Fix bug de corrección con estado conversacional

## Diagnóstico del flujo actual

En `callback_handler.py` línea 27, cuando el usuario pulsa "Corregir":
```python
context.user_data.pop("pending", None)   # BUG: borra el contexto original
```
El siguiente mensaje del empleado entra a `text_handler` o `audio_handler` sin ningún estado → se clasifica como mensaje nuevo.

## Plan de implementación

### Paso 1 — `callback_handler.py`
- [x] En el branch `elif action == "correct"`: **no** hacer `pop("pending")`.
- [x] Agregar `context.user_data["awaiting_correction"] = True`
- [x] Agregar `context.user_data["correction_started_at"] = datetime.now().isoformat()`
- [x] Cambiar texto del mensaje a: `"✏️ Decime qué corregir o agregar (texto o audio). Recuerdo lo que reportaste antes y lo reproceso con tu corrección."`
- [x] Agregar import de `datetime` al tope del archivo.

### Paso 2 — Lógica de corrección compartida (inline, no nuevo archivo) ✅

En `text_handler.py` y `audio_handler.py`, al inicio de cada handler, antes de procesar:

```
1. ¿awaiting_correction es True?
   Sí → verificar timeout (>5 min desde correction_started_at)
         Sí → limpiar estado, avisar, ir por ruta normal
         No → guardar pending como previous_context, limpiar estado corrección,
               ir por ruta de corrección (llamar process_message con previous_context)
   No → ruta normal
```

La limpieza del estado (ambos handlers, cualquier ruta):
```python
previous = context.user_data.pop("pending", None)
context.user_data.pop("awaiting_correction", None)
context.user_data.pop("correction_started_at", None)
```

Timeout: `datetime.fromisoformat(started_at) < datetime.now() - timedelta(minutes=5)`

### Paso 3 — `text_handler.py`
- [ ] Importar `datetime`, `timedelta`
- [ ] Agregar función helper `_check_correction_state(context)` → devuelve `previous_context` dict o `None`
  - Devuelve `None` si no hay `awaiting_correction`
  - Devuelve `None` + limpia estado si hay timeout → además retorna flag `timed_out=True` para avisar
  - Devuelve el `pending` guardado si está dentro de timeout → limpia estado
- [ ] En `handle_text`: al inicio, llamar helper. Si hay `previous_context`, llamar `process_message(..., previous_context=previous_context)`. Si `timed_out`, mandar aviso.

Nota: el helper es una función simple en el mismo archivo, no una clase ni un módulo aparte. Misma función se copia en `audio_handler.py` — son 10 líneas, no vale la abstracción compartida por ahora.

### Paso 4 — `audio_handler.py`
- [ ] Mismo cambio que `text_handler.py`. La detección de corrección va **antes** del download del audio (evita bajar el archivo si vamos a descartar por timeout).

### Paso 5 — `brain.py`
- [ ] Nueva firma:
  ```python
  def process_message(
      input: str,
      employee: dict,
      *,
      is_audio: bool = False,
      language_hint: str | None = None,
      previous_context: dict | None = None,  # NUEVO
  ) -> dict:
  ```
- [ ] Pasar `previous_context` a cada llamada de `classify()` en la función.
- [ ] Sin otro cambio.

### Paso 6 — `classifier.py`
- [ ] Nueva firma: `def classify(message: str, employee: dict, previous_context: dict | None = None) -> dict:`
- [ ] Si `previous_context` viene, construir un bloque adicional en `prompt`:
  ```
  El empleado ya envió un mensaje anteriormente que se clasificó así:
  - Mensaje original: "{previous_context['original_text']}"
  - Tipo asignado: {previous_context['result']['tipo']}
  - Descripción generada: {previous_context['result']['descripcion']}

  Ahora está aclarando o corrigiendo ese reporte con información adicional.
  Reclasifica considerando AMBAS piezas juntas, no solo la nueva.

  Información adicional del empleado:
  ```
  ...y luego el mensaje nuevo.
- [ ] Sin tocar `SYSTEM_PROMPT`.

### Paso 7 — `tests/test_correction_flow.py`
- [ ] **Test 1 (happy path texto):** mock `classify` que retorna un resultado fijo → simular pulsación "Corregir" → mandar corrección → verificar que `classify` recibió `previous_context` con el resultado original.
- [ ] **Test 2 (timeout):** igual que Test 1 pero `correction_started_at` puesto 6 min en el pasado → verificar que `classify` recibe `previous_context=None` y se manda aviso de timeout.
- [ ] **Test 3 (audio en corrección):** simular mensaje original por texto → "Corregir" → corrección por audio (mock de transcripción) → verificar que `classify` recibió `previous_context`.

Los tests usan `AsyncMock` de `unittest.mock` para simular `update` y `context` de python-telegram-bot. No hacen llamadas reales a Telegram ni a Gemini.

## Estructura de `context.user_data` después del fix

| Clave | Cuándo existe |
|-------|--------------|
| `pending` | Después de clasificar, antes de confirmar/corregir |
| `awaiting_correction` | True solo entre "Corregir" y el siguiente mensaje |
| `correction_started_at` | Isoformat de cuando se pulsó "Corregir" |

## Criterio de éxito

Los 3 tests pasan con `pytest tests/test_correction_flow.py`.

## Para después (no en este sprint)

- Si el usuario pulsa "Corregir" dos veces seguidas sin mandar mensaje (edge case poco probable), el segundo pulso sobreescribiría `correction_started_at` con el pending ya correcto → comportamiento aceptable, no arreglar ahora.
- El texto del aviso de timeout es en español; si el empleado usa otro idioma podría ser raro → mejora multiidioma para después.
- Los tests de corrección no cubren el caso de error de Gemini durante la reclasificación → agregar en sprint futuro de robustez.
