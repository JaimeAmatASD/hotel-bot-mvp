# hotel-bot-mvp

Bot Telegram para gestión de incidencias hoteleras con IA (Gemini + Groq Whisper).

## Stack
- LLM: `google-genai` (NO `google-generativeai`) — modelo `gemini-2.5-flash`
- STT: `groq` — Whisper Large v3 Turbo
- Telegram: `python-telegram-bot` v20+ (async-first)
- DB: SQLite via `storage.py`

## Arquitectura
- `permissions.py` — toda lógica de roles (EMPLEADO/ENCARGADO/GERENTE_GENERAL)
- `classifier.py` — clasifica mensajes; puede devolver dict o list[dict] desde Gemini (se desenvuelve con `data[0]`)
- `report_processor.py` — cierre manual y por timeout de reportes
- `handlers/` — no contienen lógica de negocio, solo enrutamiento

## Gotchas
- `gh` CLI no está instalado; crear PRs manualmente en GitHub
- Los archivos `Carga` y `El` en raíz son vacíos y accidentales — eliminar
- `employees.json` contiene IDs ficticios hasta testing real con hotel

## Workflow
Escribir plan y esperar aprobación del usuario ANTES de implementar cualquier feature.
