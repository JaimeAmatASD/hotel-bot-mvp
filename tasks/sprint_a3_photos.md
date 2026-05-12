# Sprint A.3 — Soporte de fotos (multimodal)

## Decisiones de diseño

### 1. Cómo preservar la foto en el flujo corrección/followup

`pending` ya guarda `{"result": ..., "original_text": ...}`. Para fotos, se añade
`"image_path"` al mismo dict:
```python
context.user_data["pending"] = {
    "result": result,
    "original_text": caption or "",
    "image_path": str(photo_path),   # NUEVO — solo en mensajes con foto
}
```

Cuando hay corrección o followup, `brain.process_message` recibe `previous_context`
y extrae `image_path` de ahí si no se le pasa uno directo. Así el reprocesado usa
la foto original sin que los handlers tengan que saber nada.

### 2. Migración de `classifications` (columna photo_path)

`ALTER TABLE classifications ADD COLUMN photo_path TEXT` si la columna no existe.
Chequeo con `PRAGMA table_info` dentro de `init_db()`. Idempotente.

### 3. Tests sin fotos reales

Los 5 tests mockean `process_message` (igual que A.1/A.2). Para simular la
descarga de Telegram se usa un JPEG mínimo (1×1 px, ~600 bytes) generado
en el propio test con base64. No hace falta ningún fixture externo.

## Plan de implementación

### Paso 1 — `storage.py`
- [ ] En `init_db()`: añadir bloque `PRAGMA table_info` + `ALTER TABLE` si falta `photo_path`
- [ ] En `save()`: persistir `result.get("_meta", {}).get("photo_path")` en la nueva columna

### Paso 2 — `classifier.py`
- [ ] Nueva firma: `classify(message, employee, previous_context=None, image_path=None)`
- [ ] Añadir bloque al SYSTEM_PROMPT sobre cómo tratar imágenes (ver enunciado)
- [ ] Si `image_path` llega: leer bytes, construir `contents` como lista
  `[prompt_str, types.Part.from_bytes(data=bytes, mime_type="image/jpeg")]`
  en lugar del string plano actual
- [ ] Sin `image_path`: `contents=prompt` como ahora (sin romper nada existente)

### Paso 3 — `brain.py`
- [ ] Nueva firma: `process_message(..., image_path: str | None = None)`
- [ ] Si `image_path` es None pero `previous_context` tiene `"image_path"`:
  usar ese (foto original en correcciones)
- [ ] Pasar `image_path` efectivo a `classify()` en las dos llamadas (texto y audio
  no usan imagen normalmente, pero el parámetro queda disponible para el futuro)
- [ ] En `_meta` del result de texto: añadir `"photo_path": image_path or None`

### Paso 4 — `handlers/photo_handler.py` (nuevo)
- [ ] Misma estructura que `audio_handler.py`:
  - `get_debug_mode` al inicio
  - `_pop_followup_state` / `_pop_correction_state` (copiar helpers)
  - Descargar foto más grande (`update.message.photo[-1]`)
  - Guardar en `data/photos/{telegram_id}/{timestamp}_{file_id[:12]}.jpg`
  - Llamar `brain.process_message(caption or "", employee, image_path=path)`
  - Mismo flujo de confianza / followup / resumen que text y audio handler
  - `pending` incluye `"image_path": str(path)`
- [ ] Mensaje de espera: `"📸 Procesando foto..."`

### Paso 5 — `bot.py`
- [ ] Importar `handle_photo` desde `handlers.photo_handler`
- [ ] `app.add_handler(MessageHandler(filters.PHOTO, handle_photo))`

### Paso 6 — `tests/test_photo_flow.py`
- [ ] JPEG mínimo 1×1 px inline en base64 — se escribe a `tmp_path` por test
- [ ] 5 tests con mock de `process_message` (ver criterio de éxito del enunciado)

## Notas de implementación

- `update.message.caption` tiene el texto de la foto. Si es None → string vacío al brain.
- El path de la foto se guarda relativo en `_meta["photo_path"]` para que `storage.save`
  lo pueda persistir sin cambiar la firma de `save()`.
- En el bloque `previous_context` del clasificador, si hay `image_path` en el contexto
  anterior, mencionar en el bloque de texto que "el empleado adjuntó una foto en el mensaje
  anterior" para que Gemini sepa que la imagen que recibe es la original.

## Criterio de éxito
- `pytest tests/test_photo_flow.py` → 5/5
- `pytest tests/` → 24/24 sin regresión
- 8 pasos manuales desde Telegram + foto en disco + columna en SQLite

## Para después (no en este sprint)
- Mostrar fotos en dashboard Streamlit
- Múltiples fotos → Telegram las manda como mensajes separados, cada una independiente
- Google Drive sync post-piloto
- Borrado automático de fotos antiguas (política de retención Sprint C)
