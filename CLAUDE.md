# hotel-bot-mvp

Bot Telegram para gestión de incidencias hoteleras con IA (Gemini + Groq Whisper).

Por qué es así: `decisions.md`. Errores que ya nos comimos: `tasks/lessons.md`.
Cómo tiene que salir el output del bot: `references.md`.

## Con quién estás trabajando

Jaime dirige este proyecto pero no lee código. No se lo mandes.

- Nada de diffs. Se le muestra: qué hace ahora en idioma del dominio, qué escenarios
  pasan, el estado de la suite, y qué tiene que mirar él.
- Términos técnicos: cinco palabras entre paréntesis y seguir.
- Preguntale lo que solo él sabe (qué sería un desastre en el hotel, si un mensaje al
  empleado suena bien). No le preguntes qué librería usar: eso se decide y se informa.

## Stack
- LLM: `google-genai` (NO `google-generativeai`) — modelo `gemini-2.5-flash`
- STT: `groq` — Whisper Large v3 Turbo
- Telegram: `python-telegram-bot` v20+ (async-first)
- DB: SQLite via `storage/` (paquete)
- Sheets: `gspread` + `google-auth` — capa de visibilidad de solo-lectura via `sheets_sync.py`

## Arquitectura por capas

```
domain/      → entidades puras (Employee, Incident) — sin I/O, opcional
config/      → enums (StrEnum) + rules constants
permissions.py, brain.py, classifier.py, transcriber.py  → servicios de dominio/aplicación
storage/     → paquete con módulos por dominio (schema, classifications, events, reports, ...)
notifier/    → paquete: format, send, dispatch, filters, state_change, sender (port)
presenters/  → formatters, keyboards, constants — capa de presentación
handlers/    → routing Telegram delgado (text, audio, photo, callback, command)
  _state.py, _flow.py → helpers compartidos
sheets_sync.py → espejo Google Sheets; SQLite sigue siendo la única fuente de verdad
```

## Invariantes críticos

- **Ciclo de vida (work-order, 6 estados)**: `NUEVA → ASIGNADA → EN_PROCESO → RESUELTA → CERRADA` (+ `CANCELADA` desde cualquier estado no terminal). `config/transitions.py` es la ÚNICA fuente de verdad de la máquina de estados (`ACTION_TO_STATE`, `EXPECTED_FROM`, `MANAGEMENT_ACTIONS`/`EXECUTION_ACTIONS`). Verbos: `tomar/asignar/reasignar/comenzar/terminado/validar/reabrir/cancelar`.
- **Callback format**: 3 partes siempre — `incident_action:{id}:{action}`, `assign_to:{id}:{telegram_id}`, `assign_dept:{id}:{depto}`. El actor SIEMPRE sale de `query.from_user.id`, nunca del callback.
- **`update_incident_state_atomic` en `storage/events.py`** es la ÚNICA función de transición de estado; recibe `action=` explícito y escribe trazabilidad (`assigned_by/resolved_by/closed_by/cancelled_by`). `reabrir` conserva el asignado.
- **Permisos por acción**: `permissions.can_do_action(user, incident, action)`. Gestión (asignar/validar/etc.) = manager con alcance; ejecución (comenzar/terminado) = el asignado o un manager.
- **`storage.init_db()` se llama una sola vez** al arranque del bot. Los tests inicializan explícitamente tras `patch.object(storage, "DB_PATH", ...)`.
- **Magic strings prohibidos**: usar `config.enums` (IncidentState, ReportType, Role, Priority, NotificationMode). StrEnum mantiene compat con strings en SQLite.
- **Notificaciones paralelas**: `notify_incident` usa `asyncio.gather(..., return_exceptions=True)`. Al asignar → `notify_assignee`; al resolver → `notify_managers_resolved`; al cerrar → aviso al reporter (`notify_employee_state_change`).

## Gotchas

- `gh` CLI no está instalado; crear PRs manualmente en GitHub
- `config/employees.json` (versionado) tiene solo IDs ficticios; los empleados reales de testing (Jaime, Juan) viven en `config/employees.local.json` (gitignoreado), que `load_employees()` mergea al arrancar. Si el bot corre en otra máquina, copiar ese archivo a mano.
- `GOOGLE_SERVICE_ACCOUNT_JSON` y `SHEET_ID` requeridos en `.env` para sync a Sheets (Google Sheets API habilitada en proyecto GCP 726520795387)
- `test_cases.py`, `test_extended.py`, `test_cross_department.py` en raíz son **archivos de datos** (no tests) importados por `evaluate.py` y `dashboard.py` — no moverlos a `tests/`

## Testing

- Suite normal: `venv/bin/pytest -q` → 299 tests verdes, 9 integration deselected.
- Suite completa con APIs reales: `venv/bin/pytest -q -o addopts=''` → incluye integration Gemini/Groq.
- Escenarios hoteleros E2E fake: `tests/test_hotel_scenarios.py` cubre empleado → confirmación → notificación, consultas gerente, followup, ciclo work-order completo (tomar/comenzar/terminado/validar), delegación encargado→empleado + reabrir, rechazo por permisos, reporte de turno y visibilidad de historial.
- Integration tests de audio usan fixtures reales en `audios/`; no moverlos a `tests/integration/audios/`.

## Cómo trabajar acá

- **Escribir el plan y esperar luz verde ANTES de implementar cualquier feature.**
- **Cambios chicos y verificables.** Uno por vez, suite en verde entre uno y otro.
- **No sobre-ingeniería.** Esto es un bot de hotel, no una plataforma. Si una función
  alcanza, no armes una jerarquía de clases. Si no hay tres casos, no hay abstracción.
- **No toques lo que no te pidieron.** Si ves algo mal al lado, avisá; no lo arregles
  de prepo. Si TU cambio deja algo huérfano, eso sí se limpia.
- **"Listo" significa suite en verde.** Correla antes de reportar.
- **Dos intentos y frenás.** Si un fix no sale en dos vueltas, explicá qué probaste y
  qué necesitás para destrabarlo.
- **Suite verde no significa que el bot responda bien.** Protege la estructura, no el
  texto que le llega al empleado. Una salida generada que nadie leyó se reporta como
  "sin revisar".

## El loop de aprendizaje

1. **Antes de una tarea no trivial**, leé `tasks/lessons.md`. Si lo que vas a hacer ya
   figura como error, no lo repitas.
2. **Todo bug arreglado deja dos cosas**: un test que lo reproduce (rojo antes que
   verde) y una línea en `tasks/lessons.md` escrita como prohibición, no como consejo.
3. **Toda bifurcación real** —donde se podía ir para dos lados— se anota en
   `decisions.md` con su costo aceptado. Si no hay costo, no era una decisión.
4. **Todo output del bot que salga notablemente bien o mal** se pega en `references.md`.
   Un anti-ejemplo enseña más que tres párrafos de convención.

<!-- Lo que tenga que cumplirse sí o sí no alcanza con estar escrito acá: va también
     como deny o hook en .claude/settings.json. -->

Convenciones que aplican solo a ciertos archivos viven en `.claude/rules/`.
