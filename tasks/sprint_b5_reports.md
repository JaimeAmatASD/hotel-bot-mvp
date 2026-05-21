# Sprint B.5-reportes — Reportes acumulativos de turno

## Análisis del código actual

### Handlers (text/audio/photo)
Estructura idéntica en los 3: employee check → followup/correction state → process. El check de
reporte abierto va ANTES de followup/correction: en modo reporte, los mensajes se acumulan
sin pasar por el clasificador. El estado followup/correction queda huérfano (aceptable — el
empleado eligió abrir un reporte).

### `brain.process_message` y `transcriber`
`brain.py` transcribe + clasifica en una sola llamada. Para audios en modo reporte necesitamos
solo transcripción. Solución: llamar `transcriber.transcribe(path, language_hint)` directamente.

### `settings.py`
Solo 2 variables hoy. Añadir `REPORT_TIMEOUT_HOURS = 12` y las listas de keywords.

### `bot.py`
Usa `app.run_polling()` sin JobQueue configurado. El JobQueue de python-telegram-bot v20 está
disponible via `app.job_queue` — solo hay que activarlo y añadir el job.

### `callback_handler.py`
Patrón existente: `if action.startswith("report_confirm_all:")` → rama nueva, igual que B.3
con `incident_action:*`. El handler de reporte maneja su propio `query.answer()`.

---

## Decisiones de diseño

### Keyword detection: normalizar + comparar
```python
def _normalize(text: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()
```
Comparar `_normalize(text)` contra `_normalize(keyword)` para cada keyword. Robusto a tildes
y mayúsculas. Función pura, testeable. Va en `report_processor.py`.

### Pending items en user_data, NO en DB
El resumen pre-confirmación vive en `context.user_data["pending_report"]`:
```python
{"report_id": 12, "items": [{"content": "...", "result": {...}, "message_type": "text", "photo_path": None}]}
```
Solo se persiste en `classifications` cuando el empleado confirma.

### `report_processor.py` en raíz
Misma capa que `brain.py` y `notifier.py`. Accede a `storage`, `brain`, `notifier`.

### JobQueue: run_repeating cada hora
```python
app.job_queue.run_repeating(check_expired_reports, interval=3600, first=60)
```
En el job callback: `storage.get_expired_open_reports(REPORT_TIMEOUT_HOURS)` → procesar y cerrar cada uno.

### Corrección de reporte: "rehacer todo" vs item específico
En modo corrección de reporte, el texto del usuario se detecta:
- `_normalize(text)` contiene "rehacer" → limpiar pending, reabrir reporte (estado OPEN)
- Caso contrario → reclasificar con `brain.process_message(correction_text, employee, previous_context=item_result)`

### Manager notification: solo mode="todo"
El resumen de reporte NO es una incidencia crítica. Solo llega al gerente si `mode == "todo"`.

---

## Pasos de implementación

### Paso 1 — `config/settings.py`
```python
REPORT_TIMEOUT_HOURS = 12
REPORT_OPEN_KEYWORDS = ["inicio reporte", "inicio de reporte", "abrir reporte"]
REPORT_CLOSE_KEYWORDS = ["cierre de reporte", "cerrar reporte", "fin reporte"]
```

### Paso 2 — `storage.py`
**2a. Nuevas tablas + índices** en `init_db()`:
```sql
CREATE TABLE IF NOT EXISTS reports (...)
CREATE TABLE IF NOT EXISTS report_messages (...)
CREATE INDEX IF NOT EXISTS idx_reports_employee ON reports(employee_telegram_id)
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status)
CREATE INDEX IF NOT EXISTS idx_report_messages_report ON report_messages(report_id)
```

**2b. Migración** de `classifications`: añadir `report_id INTEGER REFERENCES reports(id)` con
el patrón existente de PRAGMA table_info.

**2c. Añadir "REPORT": "REP"** a `_DISPLAY_PREFIXES` para `generate_display_id`.

**2d. 8 funciones nuevas**:
- `open_report(employee) -> int` — devuelve existente si ya está abierto
- `get_open_report_for_employee(telegram_id) -> dict | None`
- `add_message_to_report(report_id, message_type, content, photo_path=None) -> int`
- `get_report_messages(report_id) -> list[dict]` — ordenados ASC
- `close_report(report_id, closure_type="manual") -> None`
- `get_report_with_items(report_id) -> dict` — reporte + mensajes + classifications asociadas
- `link_classification_to_report(classification_id, report_id) -> None`
- `get_expired_open_reports(timeout_hours=12) -> list[dict]`

### Paso 3 — `report_processor.py` (nuevo)
```python
def is_open_keyword(text: str) -> bool
def is_close_keyword(text: str) -> bool

async def process_report_at_closure(report_id, employee, employees) -> dict:
    """Lee mensajes, clasifica cada uno con brain, devuelve decomposed dict sin guardar."""

def format_report_summary(report, decomposed, employee) -> str:
    """Texto del resumen que ve el empleado + keyboard [✅ Todo bien] [✏️ Algo está mal]"""

def format_report_for_manager(report, decomposed, display_id) -> str:
    """Mensaje corto para GERENTE_GENERAL."""

async def save_confirmed_report_items(report_id, items, employee, employees, bot) -> None:
    """Guarda en classifications con report_id, dispara notificaciones de INCIDENCIAS,
    notifica al gerente con resumen."""
```

**`REPORT_KEYBOARD`**: `InlineKeyboardMarkup` con botones `report_confirm_all:{N}` y `report_correct:{N}`.

### Paso 4 — Handlers (text/audio/photo): insertar check de reporte abierto

En los 3 handlers, ANTES del bloque followup/correction:

```python
tid = update.effective_user.id
open_report = storage.get_open_report_for_employee(tid)

if open_report:
    text_content = update.message.text or update.message.caption or ""
    if report_processor.is_close_keyword(text_content):
        await _handle_report_close(update, context, open_report, employee)
        return
    # acumular
    await _accumulate_to_report(update, context, open_report, employee)
    return

if update.message.text and report_processor.is_open_keyword(update.message.text):
    await _handle_report_open(update, context, employee)
    return
```

Funciones auxiliares `_handle_report_open`, `_handle_report_close`, `_accumulate_to_report`
van en cada handler (o extraídas a `report_processor.py` como funciones async).

Para **audio en report mode**: `transcriber.transcribe(tmp_path, language_hint=employee.get("idioma"))`.
Para **foto en report mode**: descargar (misma lógica que hoy), guardar photo_path.

### Paso 5 — `handlers/command_handler.py`
**`handle_reporte(update, context)`**:
- Sin args: abrir reporte (o avisar que hay uno abierto)
- Con args `["REP-N"]` o `["N"]`: mostrar vista del reporte vía `storage.get_report_with_items`

**`handle_fin(update, context)`**:
- Sin reporte abierto → "No tenés ningún reporte abierto."
- Con reporte abierto → `process_report_at_closure` → mostrar resumen + keyboard

### Paso 6 — `handlers/callback_handler.py`
Branch nuevo ANTES del `query.answer()` del top:
```python
if action.startswith("report_confirm_all:"):
    await _handle_report_confirm(query, context)
    return
if action.startswith("report_correct:"):
    await _handle_report_correct_start(query, context)
    return
```

`_handle_report_confirm`: llama `save_confirmed_report_items`, responde al empleado.

`_handle_report_correct_start`: setea `context.user_data["awaiting_report_correction"]`,
pide al usuario qué corregir.

En `handle_text` (ya en Paso 4): si `awaiting_report_correction`, detectar "rehacer todo"
vs corrección específica.

### Paso 7 — `handlers/__init__.py`
Actualizar `get_help_text` para añadir `/reporte` y `/fin` según rol.

### Paso 8 — `bot.py`
```python
from handlers.command_handler import handle_reporte, handle_fin
app.add_handler(CommandHandler("reporte", handle_reporte))
app.add_handler(CommandHandler("fin", handle_fin))

async def check_expired_reports(context):
    from config.settings import REPORT_TIMEOUT_HOURS
    from report_processor import close_report_with_timeout
    expired = storage.get_expired_open_reports(REPORT_TIMEOUT_HOURS)
    for report in expired:
        await close_report_with_timeout(context.bot, report, context.bot_data["employees"])

app.job_queue.run_repeating(check_expired_reports, interval=3600, first=60)
```

---

## Tests — `tests/test_reports.py` (15 mínimos)

| # | Test | Módulo |
|---|------|--------|
| 1 | `open_report` crea reporte OPEN y devuelve id | storage |
| 2 | `open_report` con reporte ya abierto devuelve el existente | storage |
| 3 | `add_message_to_report` añade y devuelve message_id | storage |
| 4 | `get_report_messages` devuelve ordenados por timestamp ASC | storage |
| 5 | `close_report` marca CLOSED con timestamp y closure_type | storage |
| 6 | `get_expired_open_reports` con timeout 0h devuelve reportes abiertos | storage |
| 7 | `is_open_keyword` matchea "inicio reporte", "INICIO REPORTE", "inicio de reporte" | report_processor |
| 8 | `is_close_keyword` matchea "cierre de reporte", "cerrar reporte", "fin reporte" | report_processor |
| 9 | `is_open_keyword` NO matchea mensaje normal | report_processor |
| 10 | `is_close_keyword` NO matchea mensaje normal | report_processor |
| 11 | `is_open_keyword` con tildes: "inicio répórte" matchea | report_processor |
| 12 | `format_report_summary` contiene sección de incidencias si hay ≥1 | report_processor |
| 13 | `format_report_summary` muestra count correcto por tipo | report_processor |
| 14 | `link_classification_to_report` setea report_id correctamente | storage |
| 15 | `get_report_with_items` devuelve reporte + mensajes + items clasificados | storage |

---

## Para después (fuera de este sprint)

- Configuración de timeout por hotel/empleado (backlog post-piloto; hoy hardcoded via settings)
- Edición de items individuales ya confirmados (reapertura de reporte)
- Reportes con coautoría (múltiples empleados)
- Vista de reporte en Google Sheets (sprint posterior)
- Trazabilidad de eventos del reporte en `incident_events`
- `/reporte REP-N` para empleado mostrando solo su propio reporte si no tiene permiso completo
- La tabla `reports` podría indexarse también por `status + started_at` para queries de timeout más eficientes
