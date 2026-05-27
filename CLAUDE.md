# hotel-bot-mvp

Bot Telegram para gestión de incidencias hoteleras con IA (Gemini + Groq Whisper).

## Stack
- LLM: `google-genai` (NO `google-generativeai`) — modelo `gemini-2.5-flash`
- STT: `groq` — Whisper Large v3 Turbo
- Telegram: `python-telegram-bot` v20+ (async-first)
- DB: SQLite via `storage.py`
- Sheets: `gspread` + `google-auth` — capa de visibilidad de solo-lectura via `sheets_sync.py`

## Arquitectura
- `permissions.py` — toda lógica de roles (EMPLEADO/ENCARGADO/GERENTE_GENERAL)
- `classifier.py` — clasifica mensajes; puede devolver dict o list[dict] desde Gemini (se desenvuelve con `data[0]`)
- `report_processor.py` — cierre manual de reportes de turno
- `sheets_sync.py` — espejo a Google Sheets; SQLite es la única fuente de verdad; si Sheets falla, el bot no se cae
- `handlers/` — no contienen lógica de negocio, solo enrutamiento
- `notifier.py` — notificaciones a encargados/gerente; `build_keyboard_for_state(incident_id, estado)` sin actor en callback
- `update_incident_state_atomic` en `storage.py` — ÚNICA función de transición de estado de incidencia

## Gotchas
- `gh` CLI no está instalado; crear PRs manualmente en GitHub
- `employees.json` — la mayoría de IDs son ficticios excepto los de testing real (Jaime 7391337590, Juan 8709342265)
- Callback format: `incident_action:{id}:{action}` (3 partes) — el actor siempre sale de `query.from_user.id`, nunca del callback
- `GOOGLE_SERVICE_ACCOUNT_JSON` y `SHEET_ID` requeridos en `.env` para el sync a Sheets

## Workflow
Escribir plan y esperar aprobación del usuario ANTES de implementar cualquier feature.
