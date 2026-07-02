# hotel-bot-mvp

Bot de Telegram para gestión de incidencias hoteleras con IA. Los empleados reportan por texto, audio o foto; el bot clasifica con Gemini, notifica a los responsables y gestiona el ciclo de vida completo de cada incidencia con botones inline — desde el reporte hasta la validación del gerente.

## Qué hace

- **Reporte sin fricción**: el empleado escribe o manda un audio ("hay un goteo en el aire de la 204") y el bot lo convierte en una incidencia estructurada (categoría, ubicación, prioridad). Si falta un dato crítico, pregunta.
- **Clasificación IA**: Gemini 2.5 Flash distingue INCIDENCIA / OBSERVACION / GUEST_INTEL / NO_REPORTE. Los audios se transcriben con Whisper (Groq) en el idioma del empleado.
- **Notificaciones por rol**: encargados reciben lo de su departamento; el gerente general filtra señal/ruido con `/notificaciones` (las CRITICA llegan siempre).
- **Ciclo de vida work-order**: `NUEVA → ASIGNADA → EN_PROCESO → RESUELTA → CERRADA` (+ `CANCELADA`), con delegación a personas o departamentos, validación/reapertura del gerente y trazabilidad completa (quién asignó, resolvió, validó).
- **Consultas**: `/abiertas`, `/hab 204`, `/buscar`, `/historial`, `/mistareas` (tareas del empleado), `/porvalidar` (cola del gerente).
- **Informe de turno**: `/reporte` genera un resumen acumulativo del turno; `/reporte sector` consolida el sector completo (read-only, encargado/gerente).
- **Espejo en Google Sheets**: capa de visibilidad de solo lectura; SQLite sigue siendo la única fuente de verdad.

## Stack

- IA: Gemini 2.5 Flash (`google-genai`) para clasificación · Whisper Large v3 Turbo (Groq) para transcripción
- Bot: `python-telegram-bot` v20+ (async)
- Persistencia: SQLite (paquete `storage/`, eventos append-only para auditoría)
- Visibilidad: `gspread` → Google Sheets
- Dashboard de evaluación del clasificador: Streamlit

## Arquitectura

Capas separadas por paquetes: `config/` (enums + reglas), `permissions.py` / `brain.py` (dominio), `storage/` (persistencia por dominio), `notifier/` (envío paralelo), `presenters/` (formato + teclados), `handlers/` (routing Telegram delgado). Detalles e invariantes en [CLAUDE.md](CLAUDE.md); specs de diseño en `docs/superpowers/`.

## Setup

```bash
python -m venv venv
venv/bin/pip install -r requirements.txt
```

Variables en `.env`:

| Variable | Para qué |
|----------|----------|
| `TELEGRAM_BOT_TOKEN` | Bot de Telegram (BotFather) |
| `GEMINI_API_KEY` | Clasificador (Google AI Studio) |
| `GROQ_API_KEY` | Transcripción de audio |
| `GOOGLE_SERVICE_ACCOUNT_JSON`, `SHEET_ID` | Sync a Google Sheets (opcional) |
| `NOTIFICATION_REDIRECT_MODE` | `admin` en testing, `off` en producción |
| `REPORT_NOTIFY_GERENTE` | Flag del aviso al gerente al cerrar informe de turno |

Arrancar: `venv/bin/python bot.py`. Los empleados y roles (EMPLEADO / ENCARGADO / GERENTE_GENERAL) se definen en `config/employees.json`.

## Tests

```bash
# Suite normal (232 tests, sin llamadas reales a APIs)
venv/bin/pytest -q

# Suite completa, incluyendo integration tests Gemini/Groq
venv/bin/pytest -q -o addopts=''

# Protocolo hotelero E2E (empleado, encargado, gerente)
venv/bin/pytest -q tests/test_hotel_scenarios.py
```

## Uso del cerebro desde otro módulo

```python
from brain import process_message

# Texto:
result = process_message(
    "Hay un goteo en el aire acondicionado de la 204",
    {"nombre": "María", "departamento": "HOUSEKEEPING", "idioma": "es"}
)

# Audio:
result = process_message(
    "/ruta/al/audio.ogg",
    {"nombre": "Andrei", "departamento": "MANTENIMIENTO", "idioma": "ro"},
    is_audio=True
)

print(result["tipo"], result["descripcion"])
# INCIDENCIA  Goteo en aire acondicionado habitación 204
```
