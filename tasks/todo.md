# Día 2 Sprint 1 — Transcriptor de Audio (Groq Whisper)

## Contexto

Día 1 completado: clasificador en 20/20. **No tocar nada del Día 1.**
Hoy: construir el transcriptor audio → texto con Groq Whisper Large v3 Turbo.
Día 3 integrará transcriptor + clasificador. Hoy solo validamos audio → texto.

---

## Pasos

- [x] 1. Consultar docs oficiales Groq Speech-to-Text en https://console.groq.com/docs/speech-text
       → Modelo confirmado: `whisper-large-v3-turbo`. SDK: `client.audio.transcriptions.create()` con `response_format="verbose_json"`.

- [x] 2. Modificar `requirements.txt` → agregar `groq`

- [x] 3. Modificar `.env.example` → agregar `GROQ_API_KEY=tu_groq_api_key_aqui`

- [x] 4. Crear carpeta `audios/` con `audios/README.md`

- [x] 5. Crear `audio_test_cases.py`

- [x] 6. Crear `transcriber.py`
       → Cliente lazy (se inicializa en la primera llamada, no al importar).
       → Errores devueltos en el dict, nunca excepciones.

- [x] 7. Instalar `groq` y verificar que `transcriber.py` importa sin error.

- [x] 8. Crear `evaluate_audio.py`

- [x] 9. Correr sin audios → 5/5 salteados con ⏭️, sin errores.

- [x] 10. Usuario grabó 5 audios en formato .flac (renombrados al nombre esperado).

- [x] 11. Correr con audios → **5/5 correctos**. Criterio superado.

- [x] 12. Escribir sección "Review" en este archivo.

---

## Scope — lo que NO entra en Día 2

- Integración con clasificador → Día 3
- Integración con Telegram → futuro
- Clases `Transcriber`, `AudioProcessor` → no
- Retry, backoff, caché → no
- Conversión de formatos con ffmpeg → no
- Tabs nuevas en dashboard → no
- TTS desde el script para generar audios → no (los graba el usuario)

---

## Criterio de éxito verificable

`python evaluate_audio.py` con los 5 audios grabados imprime `Audios procesados: N/5` con N >= 4.

---

## Review

### Resultado

**5/5 audios transcritos correctamente.** Criterio de éxito: ≥4/5. Superado.

### Qué se construyó

- `transcriber.py` — función `transcribe()` con cliente Groq lazy, manejo de errores en dict, `verbose_json` para obtener idioma y duración.
- `audio_test_cases.py` — 5 casos con keywords actualizadas al contenido real grabado.
- `evaluate_audio.py` — runner con normalización unicode, salta archivos ausentes.
- `audios/README.md` — instrucciones de grabación.

### Decisiones no obvias

**1. Cliente lazy en `transcriber.py`**
Inicializar el cliente Groq al importar fallaba si `GROQ_API_KEY` no estaba en `.env`. Se movió la inicialización a `_get_client()` para que el módulo importe limpio y solo falle al llamar `transcribe()`.

**2. Audios grabados con contenido libre**
El usuario grabó frases reales de hotel (no las del spec). Whisper transcribió correctamente en los tres idiomas (ES, EN, RO). Se actualizaron los `expected_keywords` para reflejar el contenido real.

**3. Formato .flac en lugar de .ogg**
Los audios llegaron como .flac. Whisper acepta ambos. Se renombraron los archivos y se actualizó `audio_test_cases.py`.

### Observaciones sobre calidad de transcripción

- **Español**: transcripción limpia, vocabulario técnico hotelero reconocido ("sauna", "spa", "tapones").
- **Inglés con mezcla español**: Whisper detectó "goteras" (palabra española) dentro de un audio en inglés — lo transcribió correctamente sin confundir idioma.
- **Rumano**: detectado e idioma asignado correctamente.

### Pendiente Día 3

- Integrar `transcribe()` + `classify()` en un pipeline `audio → texto → JSON`.
- Integrar con Telegram (recibir .ogg, transcribir, clasificar, responder).
