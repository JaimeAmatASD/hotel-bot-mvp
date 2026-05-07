# Día 3 Sprint 1 — Cerebro (brain.py)

## Contexto

Días 1 y 2 completos. Hoy se unen las dos piezas:
- `classify(message, employee)` — Gemini 2.5 Flash
- `transcribe(audio_path, language)` — Groq Whisper Large v3 Turbo

Una sola función pública `process_message()` que el bot de Telegram llamará sin saber nada de los proveedores.

**No tocar:** `classifier.py`, `transcriber.py`, `test_cases.py`, `test_extended.py`,
`audio_test_cases.py`, `dashboard.py`, `storage.py`.

---

## Pasos

- [x] 1. Escribir este todo.md y esperar luz verde.

- [x] 2. Crear `brain.py`

- [x] 3. Crear `test_brain.py`

- [x] 4. Correr `python test_brain.py` → **5/5 OK**

- [x] 5. Escribir sección "Review" en este archivo.

- [x] 6. Agregar snippet de uso al final de README.md.

- [x] 7. Commit.

---

## Criterio de éxito verificable

`python test_brain.py` → `Tests OK: N/5` con N=5 (audios presentes) o N=3 (sin audios).

---

## Futuro (fuera de scope Día 3)

- Integración Telegram → Día 4
- Persistencia SQLite desde el bot
- Wrapper async/await
- Abstracción de proveedor LLM (Gemini vs Claude, Groq vs OpenAI)

---

## Review

### Resultado

**5/5 tests OK.** Sprint 1 (Cerebro IA) cerrado completo.

### Qué se construyó

- `brain.py` — `process_message()`: función pura que unifica transcriptor y clasificador.
  - Flujo texto: classify directo + `_meta` con `input_type: "text"`.
  - Flujo audio: transcribe → si error/vacío devuelve ERROR sin gastar API de Gemini → classify + `_meta` completo.
- `test_brain.py` — 5 tests de integración cubriendo texto, audio ES, audio RO, archivo inexistente y texto vacío.

### Decisiones no obvias

**Ningún error lanza excepción.** Tanto `transcribe()` como `process_message()` devuelven dicts con `error` poblado. El bot de Telegram puede consumir la función sin try/except.

**No se llama al clasificador con transcripción vacía.** Si Whisper devuelve texto vacío o falla, `process_message()` corta antes y devuelve `tipo: "ERROR"`. Evita gastar quota de Gemini en nada.

**Groq devuelve nombres completos de idioma** ("Spanish", "Romanian"), no códigos ISO ("es", "ro"). Los tests validan contra los nombres completos.

### Observación TEST 3 (rumano)

El audio `ro_ac_105.flac` contiene "Să vă mulțumim pentru vizionare" (cierre de YouTube, no un mensaje de hotel). El clasificador devolvió `NO_REPORTE`, que es correcto dado el contenido. La assertion del test valida el pipeline (no lanza error, idioma detectado correctamente, descripcion en español), no el tipo específico.

### Estado del Sprint 1

| Día | Módulo | Estado |
|-----|--------|--------|
| 1 | `classifier.py` | ✅ 20/20 core, 88% extended |
| 2 | `transcriber.py` | ✅ 5/5 audios |
| 3 | `brain.py` | ✅ 5/5 tests |

Listo para Día 4: bot de Telegram que llame a `process_message()`.
