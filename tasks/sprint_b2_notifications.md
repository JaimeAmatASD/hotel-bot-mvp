# Sprint B.2 — Notificaciones a encargados y gerente

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Conectar `permissions.py` al bot para que al confirmar una INCIDENCIA, el encargado del departamento y el gerente general reciban notificación en su Telegram, con filtros configurables para el gerente.

**Architecture:** Nuevo módulo `notifier.py` en raíz maneja lógica de notificación, formato de mensajes y logging en SQLite. Variable de entorno `NOTIFICATION_REDIRECT_MODE=admin` redirige todas las notificaciones al admin para testing desde un solo Telegram. Filtros del gerente en tabla `user_preferences` (columnas nuevas).

**Tech Stack:** python-telegram-bot v20+ (async), SQLite via patrón existente en `storage.py`, pytest + pytest-asyncio + unittest.mock.

---

## Decisiones de diseño

**¿Por qué `notifier.py` en raíz y no en `handlers/`?**
Es un servicio de dominio que puede ser llamado desde múltiples handlers (hoy `callback_handler.py`, mañana quizás un comando de reenvío). No es un handler de Telegram — no recibe `Update`. El patrón del repo es: handlers en `handlers/`, servicios de dominio en raíz (`storage.py`, `classifier.py`, `permissions.py`).

**¿Por qué la redirección es variable de entorno y no flag por usuario?**
El modo testing/producción es un estado del servidor, no una preferencia de usuario. Cambiar `NOTIFICATION_REDIRECT_MODE=off` en `.env` al pasar a producción es un cambio explícito, no accidental.

**¿Por qué CRITICA siempre llega al gerente?**
Es la excepción diseñada: una habitación en llamas no puede filtrarse por "modo nada". Los filtros del gerente controlan la señal/ruido en condiciones normales, no en emergencias.

---

## Estructura de archivos

| Archivo | Acción | Responsabilidad |
|---------|--------|-----------------|
| `config/settings.py` | Crear | Variables de entorno: ADMIN_TELEGRAM_ID, NOTIFICATION_REDIRECT_MODE |
| `.env.example` | Modificar | Documentar nuevas variables |
| `storage.py` | Modificar | save() devuelve ID, tabla notifications, funciones de preferencias, generate_display_id |
| `notifier.py` | Crear | Servicio de notificaciones: formato, envío, logging |
| `handlers/callback_handler.py` | Modificar | Llamar a notifier.notify_incident() tras confirm de INCIDENCIA |
| `handlers/command_handler.py` | Modificar | Añadir handle_notificaciones() |
| `bot.py` | Modificar | Registrar CommandHandler("/notificaciones") |
| `tests/test_notifier.py` | Crear | 12+ tests del notifier |
| `tasks/lessons.md` | Modificar | Lecciones del sprint |

---

## Task 1: config/settings.py + .env.example

**Files:**
- Create: `config/settings.py`
- Modify: `.env.example`

- [ ] **Step 1: Crear config/settings.py**

```python
import os

ADMIN_TELEGRAM_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", "0"))
NOTIFICATION_REDIRECT_MODE = os.environ.get("NOTIFICATION_REDIRECT_MODE", "off")
```

- [ ] **Step 2: Actualizar .env.example**

Añadir al final del archivo:
```
TELEGRAM_BOT_TOKEN=tu_bot_token_aqui
ADMIN_TELEGRAM_ID=tu_telegram_id_aqui
NOTIFICATION_REDIRECT_MODE=admin
```

(El archivo actualmente solo tiene GEMINI_API_KEY y GROQ_API_KEY — añadir las tres líneas al final.)

- [ ] **Step 3: Verificar que el módulo importa sin errores**

```bash
cd /home/jaime/hotel-bot-mvp && python3 -c "from config import settings; print(settings.NOTIFICATION_REDIRECT_MODE)"
```
Expected output: `off`

- [ ] **Step 4: Commit**

```bash
git add config/settings.py .env.example
git commit -m "feat: add ADMIN_TELEGRAM_ID and NOTIFICATION_REDIRECT_MODE config"
```

---

## Task 2: storage.save() devuelve ID + generate_display_id

**Files:**
- Modify: `storage.py`
- Create: `tests/test_notifier.py` (tests 12 solamente, los demás van en Task 5)

- [ ] **Step 1: Escribir test que falla — save() devuelve int**

En archivo nuevo `tests/test_notifier.py`:

```python
"""Tests para Sprint B.2 — notificaciones."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Test 12: generate_display_id
# ---------------------------------------------------------------------------

def test_generate_display_id_incidencia():
    from storage import generate_display_id
    assert generate_display_id("INCIDENCIA", 1) == "INC-001"
    assert generate_display_id("INCIDENCIA", 42) == "INC-042"


def test_generate_display_id_otros_tipos():
    from storage import generate_display_id
    assert generate_display_id("OBSERVACION", 15) == "OBS-015"
    assert generate_display_id("GUEST_INTEL", 8) == "MEM-008"
    assert generate_display_id("NO_REPORTE", 3) == "NR-003"
```

- [ ] **Step 2: Ejecutar para confirmar que falla**

```bash
cd /home/jaime/hotel-bot-mvp && python3 -m pytest tests/test_notifier.py::test_generate_display_id_incidencia -v
```
Expected: FAILED con `ImportError: cannot import name 'generate_display_id'`

- [ ] **Step 3: Añadir generate_display_id a storage.py**

Al final de `storage.py`, después de `get_all_history()`:

```python
_DISPLAY_PREFIXES = {
    "INCIDENCIA": "INC",
    "OBSERVACION": "OBS",
    "GUEST_INTEL": "MEM",
    "NO_REPORTE": "NR",
}


def generate_display_id(tipo: str, id: int) -> str:
    prefix = _DISPLAY_PREFIXES.get(tipo, "??")
    return f"{prefix}-{id:03d}"
```

- [ ] **Step 4: Modificar save() para devolver el ID**

Cambio quirúrgico en `storage.py`:

```python
# ANTES (línea ~68):
def save(employee: dict, message: str, result: dict):
    init_db()
    with _conn() as con:
        con.execute("""
            INSERT INTO classifications
            ...
        """, (...))

# DESPUÉS:
def save(employee: dict, message: str, result: dict) -> int:
    init_db()
    with _conn() as con:
        cur = con.execute("""
            INSERT INTO classifications
            ...
        """, (...))
        return cur.lastrowid
```

Solo cambia: `def save(...)` → `def save(...) -> int:`, y `con.execute(...)` → `cur = con.execute(...)\n        return cur.lastrowid`.

- [ ] **Step 5: Ejecutar tests para confirmar que pasan**

```bash
cd /home/jaime/hotel-bot-mvp && python3 -m pytest tests/test_notifier.py -v
```
Expected: 2 tests PASSED

- [ ] **Step 6: Verificar que tests anteriores siguen pasando**

```bash
cd /home/jaime/hotel-bot-mvp && python3 -m pytest tests/ -v --tb=short
```
Expected: todos pasan (save() antes no retornaba nada, Python silencia el valor de retorno ignorado)

- [ ] **Step 7: Commit**

```bash
git add storage.py tests/test_notifier.py
git commit -m "feat: save() returns lastrowid, add generate_display_id"
```

---

## Task 3: storage.py — tabla notifications + preferencias del gerente

**Files:**
- Modify: `storage.py`

- [ ] **Step 1: Añadir tabla notifications e init en init_db()**

Dentro de `init_db()`, después del bloque de `user_preferences`, añadir:

```python
        con.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp                 TEXT NOT NULL,
                incident_id               INTEGER NOT NULL,
                recipient_telegram_id     INTEGER NOT NULL,
                recipient_actual_telegram_id INTEGER NOT NULL,
                redirect_mode             TEXT,
                status                    TEXT NOT NULL,
                error_message             TEXT,
                FOREIGN KEY (incident_id) REFERENCES classifications(id)
            )
        """)
```

- [ ] **Step 2: Añadir migración para columnas nuevas en user_preferences**

Después del bloque de migración de `photo_path` (al final de `init_db()`), añadir:

```python
        # Migrations for user_preferences notification columns
        pref_cols = [row[1] for row in con.execute("PRAGMA table_info(user_preferences)").fetchall()]
        if "notification_mode" not in pref_cols:
            con.execute("ALTER TABLE user_preferences ADD COLUMN notification_mode TEXT DEFAULT 'criticas'")
        if "excluded_departments" not in pref_cols:
            con.execute("ALTER TABLE user_preferences ADD COLUMN excluded_departments TEXT DEFAULT ''")
```

- [ ] **Step 3: Añadir funciones de notificaciones y preferencias al final de storage.py**

```python
def save_notification(
    incident_id: int,
    recipient_telegram_id: int,
    recipient_actual_telegram_id: int,
    redirect_mode: str,
    status: str,
    error_message: str | None = None,
) -> None:
    init_db()
    with _conn() as con:
        con.execute("""
            INSERT INTO notifications
            (timestamp, incident_id, recipient_telegram_id, recipient_actual_telegram_id,
             redirect_mode, status, error_message)
            VALUES (?,?,?,?,?,?,?)
        """, (
            datetime.now().isoformat(timespec="seconds"),
            incident_id,
            recipient_telegram_id,
            recipient_actual_telegram_id,
            redirect_mode,
            status,
            error_message,
        ))


def get_notifications_for_incident(incident_id: int) -> list[dict]:
    init_db()
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM notifications WHERE incident_id = ? ORDER BY timestamp",
            (incident_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_recent_notifications(limit: int = 50) -> list[dict]:
    init_db()
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM notifications ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_notification_preferences(telegram_id: int) -> dict:
    """Returns {"mode": "criticas", "excluded_departments": [...]}"""
    init_db()
    with _conn() as con:
        row = con.execute(
            "SELECT notification_mode, excluded_departments FROM user_preferences WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()
    if not row:
        return {"mode": "criticas", "excluded_departments": []}
    excluded_raw = row["excluded_departments"] or ""
    excluded = [d.strip() for d in excluded_raw.split(",") if d.strip()]
    return {"mode": row["notification_mode"] or "criticas", "excluded_departments": excluded}


def set_notification_mode(telegram_id: int, mode: str) -> None:
    init_db()
    with _conn() as con:
        con.execute(
            """INSERT INTO user_preferences (telegram_id, notification_mode)
               VALUES (?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET notification_mode = excluded.notification_mode""",
            (telegram_id, mode),
        )


def toggle_excluded_department(telegram_id: int, departamento: str) -> bool:
    """Toggle: si estaba excluido lo quita, si no lo agrega. Devuelve True si quedó excluido."""
    prefs = get_notification_preferences(telegram_id)
    excluded = prefs["excluded_departments"]
    dept_upper = departamento.upper()
    if dept_upper in excluded:
        excluded.remove(dept_upper)
        is_excluded = False
    else:
        excluded.append(dept_upper)
        is_excluded = True
    with _conn() as con:
        con.execute(
            """INSERT INTO user_preferences (telegram_id, excluded_departments)
               VALUES (?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET excluded_departments = excluded.excluded_departments""",
            (telegram_id, ",".join(excluded)),
        )
    return is_excluded
```

- [ ] **Step 4: Verificar que storage importa y init_db() corre sin errores**

```bash
cd /home/jaime/hotel-bot-mvp && python3 -c "import storage; storage.init_db(); print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Verificar preferencias round-trip con tmp DB**

```bash
cd /home/jaime/hotel-bot-mvp && python3 -c "
import storage, tempfile, pathlib
storage.DB_PATH = pathlib.Path(tempfile.mkdtemp()) / 'test.db'
storage.init_db()
prefs = storage.get_notification_preferences(999)
print('default:', prefs)
storage.set_notification_mode(999, 'todo')
print('after set:', storage.get_notification_preferences(999))
result = storage.toggle_excluded_department(999, 'SPA')
print('toggle SPA excluded:', result)
print('prefs after toggle:', storage.get_notification_preferences(999))
"
```
Expected:
```
default: {'mode': 'criticas', 'excluded_departments': []}
after set: {'mode': 'todo', 'excluded_departments': []}
toggle SPA excluded: True
prefs after toggle: {'mode': 'todo', 'excluded_departments': ['SPA']}
```

- [ ] **Step 6: Verificar tests siguen pasando**

```bash
cd /home/jaime/hotel-bot-mvp && python3 -m pytest tests/ -v --tb=short
```
Expected: todos pasan

- [ ] **Step 7: Commit**

```bash
git add storage.py
git commit -m "feat: notifications table, preferences columns, save/get functions"
```

---

## Task 4: notifier.py — format_notification_message (función pura)

**Files:**
- Create: `notifier.py`
- Modify: `tests/test_notifier.py`

- [ ] **Step 1: Añadir tests 1 y 2 a tests/test_notifier.py**

Añadir después de los tests de generate_display_id:

```python
# ---------------------------------------------------------------------------
# Fixtures compartidas
# ---------------------------------------------------------------------------

INCIDENT_MANT = {
    "id": 42,
    "tipo": "INCIDENCIA",
    "prioridad": "ALTA",
    "categoria": "MANTENIMIENTO",
    "subcategoria": "Sanitarios",
    "ubicacion": "Habitación 305",
    "descripcion": "Goteo en el baño",
    "photo_path": None,
    "employee_name": "Jaime A",
    "employee_dept": "SPA",
}

REPORTER = {"nombre": "Jaime A", "departamento": "SPA"}

EMPLOYEES = {
    1001: {"telegram_id": 1001, "nombre": "Ana", "departamento": "SPA", "rol": "EMPLEADO"},
    2001: {"telegram_id": 2001, "nombre": "Carlos Enc Mant", "departamento": "MANTENIMIENTO", "rol": "ENCARGADO"},
    3001: {"telegram_id": 3001, "nombre": "Alfredo Gerente", "departamento": "GENERAL", "rol": "GERENTE_GENERAL"},
}


# ---------------------------------------------------------------------------
# Test 1: format_notification_message sin redirect
# ---------------------------------------------------------------------------

def test_format_notification_sin_redirect():
    from notifier import format_notification_message
    msg = format_notification_message(
        incident=INCIDENT_MANT,
        reporter=REPORTER,
        incident_id_display="INC-042",
        is_redirect=False,
        actual_recipient_name=None,
    )
    assert "INC-042" in msg
    assert "🔔 Nueva incidencia" in msg
    assert "MANTENIMIENTO" in msg
    assert "ALTA" in msg
    assert "Habitación 305" in msg
    assert "Goteo en el baño" in msg
    assert "Jaime A" in msg
    # No debe tener prefijo de testing
    assert "🧪" not in msg
    assert "Modo testing" not in msg


# ---------------------------------------------------------------------------
# Test 2: format_notification_message con redirect incluye prefijo
# ---------------------------------------------------------------------------

def test_format_notification_con_redirect():
    from notifier import format_notification_message
    msg = format_notification_message(
        incident=INCIDENT_MANT,
        reporter=REPORTER,
        incident_id_display="INC-042",
        is_redirect=True,
        actual_recipient_name="Carlos Enc Mant",
    )
    assert "🧪" in msg
    assert "Modo testing" in msg
    assert "Carlos Enc Mant" in msg
    # El contenido del mensaje sigue estando
    assert "INC-042" in msg
    assert "MANTENIMIENTO" in msg
```

- [ ] **Step 2: Ejecutar para confirmar que fallan**

```bash
cd /home/jaime/hotel-bot-mvp && python3 -m pytest tests/test_notifier.py::test_format_notification_sin_redirect tests/test_notifier.py::test_format_notification_con_redirect -v
```
Expected: FAILED con `ModuleNotFoundError: No module named 'notifier'`

- [ ] **Step 3: Crear notifier.py con format_notification_message**

```python
from datetime import datetime
from handlers import PRIORIDAD_EMOJI, TIPO_EMOJI


def format_notification_message(
    incident: dict,
    reporter: dict,
    incident_id_display: str,
    is_redirect: bool = False,
    actual_recipient_name: str | None = None,
) -> str:
    prioridad = incident.get("prioridad", "")
    categoria = incident.get("categoria", "")
    subcategoria = incident.get("subcategoria")
    ubicacion = incident.get("ubicacion", "")
    descripcion = incident.get("descripcion", "")
    reporter_name = reporter.get("nombre", "")
    reporter_dept = reporter.get("departamento", "")

    cat_str = f"{categoria} › {subcategoria}" if subcategoria else categoria
    prioridad_emoji = PRIORIDAD_EMOJI.get(prioridad, "")
    tipo_emoji = TIPO_EMOJI.get("INCIDENCIA", "🔧")

    lines = [
        f"🔔 Nueva incidencia — {incident_id_display}",
        f"{tipo_emoji} {cat_str} — {prioridad_emoji} {prioridad}",
        f"📍 {ubicacion}",
        f"📝 {descripcion}",
        "",
        f"Reportado por: {reporter_name} ({reporter_dept})",
    ]
    body = "\n".join(lines)

    if is_redirect and actual_recipient_name:
        prefix = f"🧪 [Modo testing — destinatario real: {actual_recipient_name}]\n\n"
        return prefix + body
    return body
```

- [ ] **Step 4: Ejecutar tests para confirmar que pasan**

```bash
cd /home/jaime/hotel-bot-mvp && python3 -m pytest tests/test_notifier.py::test_format_notification_sin_redirect tests/test_notifier.py::test_format_notification_con_redirect -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add notifier.py tests/test_notifier.py
git commit -m "feat: notifier.format_notification_message with redirect support"
```

---

## Task 5: notifier.py — notify_incident completo + tests 3-11

**Files:**
- Modify: `notifier.py`
- Modify: `tests/test_notifier.py`

- [ ] **Step 1: Añadir tests 3-11 a tests/test_notifier.py**

Añadir al final del archivo:

```python
# ---------------------------------------------------------------------------
# Tests 3-11: notify_incident (async, usa bot mock y storage mock)
# ---------------------------------------------------------------------------

INCIDENT_INCIDENCIA = {
    "id": 10,
    "tipo": "INCIDENCIA",
    "prioridad": "ALTA",
    "categoria": "MANTENIMIENTO",
    "subcategoria": None,
    "ubicacion": "Habitación 101",
    "descripcion": "Luz rota",
    "photo_path": None,
    "employee_name": "Ana",
    "employee_dept": "SPA",
}

INCIDENT_OBSERVACION = {
    "id": 11,
    "tipo": "OBSERVACION",
    "prioridad": None,
    "categoria": "LIMPIEZA",
    "subcategoria": None,
    "ubicacion": "Lobby",
    "descripcion": "Alfombra sucia",
    "photo_path": None,
    "employee_name": "Ana",
    "employee_dept": "SPA",
}


def make_bot():
    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock())
    bot.send_photo = AsyncMock(return_value=MagicMock())
    return bot


# Test 3: INCIDENCIA → llama send_notification_with_logging para encargado + gerente
@pytest.mark.asyncio
async def test_notify_incidencia_llama_encargado_y_gerente():
    bot = make_bot()
    with patch("notifier.storage.save_notification"), \
         patch("notifier.storage.get_notification_preferences", return_value={"mode": "todo", "excluded_departments": []}), \
         patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "off"):
        from notifier import notify_incident
        await notify_incident(bot=bot, incident=INCIDENT_INCIDENCIA, employees=EMPLOYEES, reporter_employee=REPORTER)

    # Debe haber enviado mensaje a dos destinatarios: encargado (2001) y gerente (3001)
    assert bot.send_message.call_count == 2
    called_ids = {call.kwargs["chat_id"] for call in bot.send_message.call_args_list}
    assert 2001 in called_ids
    assert 3001 in called_ids


# Test 4: OBSERVACION → NO dispara notificaciones
@pytest.mark.asyncio
async def test_notify_observacion_no_notifica():
    bot = make_bot()
    with patch("notifier.storage.save_notification"), \
         patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "off"):
        from notifier import notify_incident
        await notify_incident(bot=bot, incident=INCIDENT_OBSERVACION, employees=EMPLOYEES, reporter_employee=REPORTER)

    assert bot.send_message.call_count == 0
    assert bot.send_photo.call_count == 0


# Test 5: redirect_mode=admin → usa ADMIN_TELEGRAM_ID
@pytest.mark.asyncio
async def test_notify_redirect_usa_admin_id():
    bot = make_bot()
    with patch("notifier.storage.save_notification"), \
         patch("notifier.storage.get_notification_preferences", return_value={"mode": "todo", "excluded_departments": []}), \
         patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "admin"), \
         patch("notifier.settings.ADMIN_TELEGRAM_ID", 9999):
        from notifier import notify_incident
        import importlib, notifier as n_mod
        importlib.reload(n_mod)  # reload para que apliquen los patches de módulo
        await n_mod.notify_incident(bot=bot, incident=INCIDENT_INCIDENCIA, employees=EMPLOYEES, reporter_employee=REPORTER)

    # Todos los envíos van a 9999 (admin)
    for call in bot.send_message.call_args_list:
        assert call.kwargs["chat_id"] == 9999


# Test 6: Gerente mode=nada → NO recibe MEDIA
@pytest.mark.asyncio
async def test_gerente_modo_nada_no_recibe_media():
    bot = make_bot()
    incident_media = {**INCIDENT_INCIDENCIA, "prioridad": "MEDIA"}
    with patch("notifier.storage.save_notification"), \
         patch("notifier.storage.get_notification_preferences", return_value={"mode": "nada", "excluded_departments": []}), \
         patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "off"):
        from notifier import notify_incident
        await notify_incident(bot=bot, incident=incident_media, employees=EMPLOYEES, reporter_employee=REPORTER)

    # Solo encargado recibe (2001), no gerente (3001)
    called_ids = {call.kwargs["chat_id"] for call in bot.send_message.call_args_list}
    assert 2001 in called_ids
    assert 3001 not in called_ids


# Test 7: Gerente mode=nada → SÍ recibe CRITICA (excepción absoluta)
@pytest.mark.asyncio
async def test_gerente_modo_nada_si_recibe_critica():
    bot = make_bot()
    incident_critica = {**INCIDENT_INCIDENCIA, "prioridad": "CRITICA"}
    with patch("notifier.storage.save_notification"), \
         patch("notifier.storage.get_notification_preferences", return_value={"mode": "nada", "excluded_departments": []}), \
         patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "off"):
        from notifier import notify_incident
        await notify_incident(bot=bot, incident=incident_critica, employees=EMPLOYEES, reporter_employee=REPORTER)

    called_ids = {call.kwargs["chat_id"] for call in bot.send_message.call_args_list}
    assert 3001 in called_ids  # gerente SÍ recibe CRITICA


# Test 8: Gerente mode=criticas → recibe ALTA y CRITICA, no MEDIA ni BAJA
@pytest.mark.asyncio
async def test_gerente_modo_criticas_filtra_por_prioridad():
    from notifier import notify_incident

    async def check_prioridad(prioridad, expect_gerente):
        bot = make_bot()
        inc = {**INCIDENT_INCIDENCIA, "prioridad": prioridad}
        with patch("notifier.storage.save_notification"), \
             patch("notifier.storage.get_notification_preferences", return_value={"mode": "criticas", "excluded_departments": []}), \
             patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "off"):
            await notify_incident(bot=bot, incident=inc, employees=EMPLOYEES, reporter_employee=REPORTER)
        called_ids = {call.kwargs["chat_id"] for call in bot.send_message.call_args_list}
        assert (3001 in called_ids) == expect_gerente, f"prioridad={prioridad}, expect_gerente={expect_gerente}"

    await check_prioridad("CRITICA", True)
    await check_prioridad("ALTA", True)
    await check_prioridad("MEDIA", False)
    await check_prioridad("BAJA", False)


# Test 9: Gerente con depto excluido → no recibe de ese depto (excepto CRITICA)
@pytest.mark.asyncio
async def test_gerente_depto_excluido_no_recibe_excepto_critica():
    from notifier import notify_incident

    # ALTA de MANTENIMIENTO excluido → gerente no recibe
    bot = make_bot()
    with patch("notifier.storage.save_notification"), \
         patch("notifier.storage.get_notification_preferences",
               return_value={"mode": "todo", "excluded_departments": ["MANTENIMIENTO"]}), \
         patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "off"):
        await notify_incident(bot=bot, incident=INCIDENT_INCIDENCIA, employees=EMPLOYEES, reporter_employee=REPORTER)
    called_ids = {call.kwargs["chat_id"] for call in bot.send_message.call_args_list}
    assert 3001 not in called_ids  # gerente excluye MANTENIMIENTO

    # CRITICA de MANTENIMIENTO excluido → gerente SÍ recibe (excepción)
    bot2 = make_bot()
    incident_critica = {**INCIDENT_INCIDENCIA, "prioridad": "CRITICA"}
    with patch("notifier.storage.save_notification"), \
         patch("notifier.storage.get_notification_preferences",
               return_value={"mode": "todo", "excluded_departments": ["MANTENIMIENTO"]}), \
         patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "off"):
        await notify_incident(bot=bot2, incident=incident_critica, employees=EMPLOYEES, reporter_employee=REPORTER)
    called_ids2 = {call.kwargs["chat_id"] for call in bot2.send_message.call_args_list}
    assert 3001 in called_ids2  # CRITICA siempre llega


# Test 10: Encargado siempre recibe lo de su depto sin importar preferencias
@pytest.mark.asyncio
async def test_encargado_siempre_recibe_sin_filtros():
    from notifier import notify_incident

    # Incluso si storage.get_notification_preferences devuelve algo raro para el encargado,
    # el encargado siempre recibe — los filtros solo aplican a GERENTE_GENERAL
    bot = make_bot()
    with patch("notifier.storage.save_notification"), \
         patch("notifier.storage.get_notification_preferences", return_value={"mode": "nada", "excluded_departments": ["MANTENIMIENTO"]}), \
         patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "off"):
        await notify_incident(bot=bot, incident=INCIDENT_INCIDENCIA, employees=EMPLOYEES, reporter_employee=REPORTER)

    called_ids = {call.kwargs["chat_id"] for call in bot.send_message.call_args_list}
    assert 2001 in called_ids  # encargado siempre recibe


# Test 11: Notificación fallida → registrada con status="failed" y error_message
@pytest.mark.asyncio
async def test_notificacion_fallida_se_registra_como_failed():
    from notifier import notify_incident

    bot = make_bot()
    bot.send_message = AsyncMock(side_effect=Exception("Telegram timeout"))

    saved_notifications = []

    def mock_save_notification(**kwargs):
        saved_notifications.append(kwargs)

    with patch("notifier.storage.save_notification", side_effect=lambda **kw: saved_notifications.append(kw)), \
         patch("notifier.storage.get_notification_preferences", return_value={"mode": "todo", "excluded_departments": []}), \
         patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "off"):
        await notify_incident(bot=bot, incident=INCIDENT_INCIDENCIA, employees=EMPLOYEES, reporter_employee=REPORTER)

    failed = [n for n in saved_notifications if n.get("status") == "failed"]
    assert len(failed) >= 1
    assert failed[0]["error_message"] is not None
    assert "Telegram timeout" in failed[0]["error_message"]
```

- [ ] **Step 2: Ejecutar para confirmar que fallan**

```bash
cd /home/jaime/hotel-bot-mvp && python3 -m pytest tests/test_notifier.py -v --tb=short 2>&1 | grep -E "PASSED|FAILED|ERROR"
```
Expected: tests 1, 2, 12 PASSED; tests 3-11 FAILED/ERROR (notify_incident no existe)

- [ ] **Step 3: Completar notifier.py con notify_incident y send_notification_with_logging**

Añadir al final de `notifier.py` (después de `format_notification_message`):

```python
import storage
import permissions
from config import settings


def _should_notify_gerente(incident: dict, prefs: dict) -> bool:
    """Aplica filtros del gerente. CRITICA siempre pasa."""
    prioridad = incident.get("prioridad", "")
    mode = prefs.get("mode", "criticas")

    if prioridad == "CRITICA":
        return True
    if mode == "nada":
        return False
    if mode == "solo_criticas":
        return False
    if mode == "criticas":
        return prioridad == "ALTA"
    if mode == "todo":
        excluded = prefs.get("excluded_departments", [])
        return incident.get("categoria") not in excluded
    return True


async def send_notification_with_logging(
    bot,
    recipient_telegram_id: int,
    actual_recipient_telegram_id: int,
    message: str,
    photo_path: str | None,
    incident_id: int,
    redirect_mode: str,
) -> None:
    try:
        if photo_path:
            with open(photo_path, "rb") as f:
                await bot.send_photo(
                    chat_id=actual_recipient_telegram_id,
                    photo=f,
                    caption=message,
                )
        else:
            await bot.send_message(
                chat_id=actual_recipient_telegram_id,
                text=message,
            )
        storage.save_notification(
            incident_id=incident_id,
            recipient_telegram_id=recipient_telegram_id,
            recipient_actual_telegram_id=actual_recipient_telegram_id,
            redirect_mode=redirect_mode,
            status="sent",
        )
    except Exception as e:
        storage.save_notification(
            incident_id=incident_id,
            recipient_telegram_id=recipient_telegram_id,
            recipient_actual_telegram_id=actual_recipient_telegram_id,
            redirect_mode=redirect_mode,
            status="failed",
            error_message=str(e),
        )


async def notify_incident(
    bot,
    incident: dict,
    employees: dict,
    reporter_employee: dict,
) -> None:
    if incident.get("tipo") != "INCIDENCIA":
        return

    incident_id = incident["id"]
    display_id = storage.generate_display_id("INCIDENCIA", incident_id)
    redirect_mode = settings.NOTIFICATION_REDIRECT_MODE
    is_redirect = redirect_mode == "admin"

    recipient_ids = permissions.get_notification_recipients(incident, employees)

    for tid in recipient_ids:
        emp = employees.get(tid)
        if not emp:
            continue

        rol = emp.get("rol", "EMPLEADO")

        if rol == "GERENTE_GENERAL":
            prefs = storage.get_notification_preferences(tid)
            if not _should_notify_gerente(incident, prefs):
                continue

        actual_tid = settings.ADMIN_TELEGRAM_ID if is_redirect else tid
        recipient_name = emp.get("nombre", "")

        msg = format_notification_message(
            incident=incident,
            reporter=reporter_employee,
            incident_id_display=display_id,
            is_redirect=is_redirect,
            actual_recipient_name=recipient_name if is_redirect else None,
        )

        await send_notification_with_logging(
            bot=bot,
            recipient_telegram_id=tid,
            actual_recipient_telegram_id=actual_tid,
            message=msg,
            photo_path=incident.get("photo_path"),
            incident_id=incident_id,
            redirect_mode=redirect_mode,
        )
```

- [ ] **Step 4: Ejecutar todos los tests del notifier**

```bash
cd /home/jaime/hotel-bot-mvp && python3 -m pytest tests/test_notifier.py -v --tb=short
```
Expected: Los 14 tests PASSED (2 de generate_display_id + 2 de format + 10 de notify_incident)

**Nota sobre test 5 (redirect):** Si el reload trick no funciona bien en el entorno, simplificar el test así:
```python
@pytest.mark.asyncio
async def test_notify_redirect_usa_admin_id():
    bot = make_bot()
    with patch("notifier.storage.save_notification"), \
         patch("notifier.storage.get_notification_preferences", return_value={"mode": "todo", "excluded_departments": []}), \
         patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "admin"), \
         patch("notifier.settings.ADMIN_TELEGRAM_ID", 9999):
        from notifier import notify_incident
        await notify_incident(bot=bot, incident=INCIDENT_INCIDENCIA, employees=EMPLOYEES, reporter_employee=REPORTER)
    for call in bot.send_message.call_args_list:
        assert call.kwargs["chat_id"] == 9999
```
(La función lee `settings.NOTIFICATION_REDIRECT_MODE` y `settings.ADMIN_TELEGRAM_ID` en tiempo de ejecución, así que el patch directo al atributo del módulo funciona sin reload.)

- [ ] **Step 5: Ejecutar suite completa**

```bash
cd /home/jaime/hotel-bot-mvp && python3 -m pytest tests/ -v --tb=short
```
Expected: todos pasan

- [ ] **Step 6: Commit**

```bash
git add notifier.py tests/test_notifier.py
git commit -m "feat: notifier.notify_incident with filters, redirect, and logging"
```

---

## Task 6: callback_handler.py — integrar notifier

**Files:**
- Modify: `handlers/callback_handler.py`

- [ ] **Step 1: Modificar handle_callback para llamar al notifier tras confirm**

El cambio es quirúrgico: en el bloque `if action == "confirm":`, después de `save()`, construir el incident dict y llamar a `notify_incident`. Solo para tipo INCIDENCIA.

```python
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from handlers import get_employee
from storage import save
import notifier


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action = query.data
    pending = context.user_data.get("pending")

    if action == "confirm":
        if not pending:
            await query.edit_message_text("❌ No hay reporte pendiente.")
            return

        employee = get_employee(update, context)
        result = pending["result"]
        incident_id = save(employee, pending["original_text"], result)
        context.user_data.pop("pending", None)

        nombre = employee["nombre"].split()[0] if employee else "empleado"
        await query.edit_message_text(f"✅ Guardado. Gracias, {nombre}.")

        if result.get("tipo") == "INCIDENCIA":
            incident = {
                **result,
                "id": incident_id,
                "employee_name": employee["nombre"],
                "employee_dept": employee.get("departamento"),
                "photo_path": result.get("_meta", {}).get("photo_path"),
            }
            await notifier.notify_incident(
                bot=context.bot,
                incident=incident,
                employees=context.bot_data["employees"],
                reporter_employee=employee,
            )

    elif action == "correct":
        context.user_data["awaiting_correction"] = True
        context.user_data["correction_started_at"] = datetime.now().isoformat()
        await query.edit_message_text(
            "✏️ Decime qué corregir o agregar (texto o audio). Recuerdo lo que reportaste antes y lo reproceso con tu corrección."
        )
```

- [ ] **Step 2: Verificar que los tests de callback siguen pasando**

```bash
cd /home/jaime/hotel-bot-mvp && python3 -m pytest tests/ -v --tb=short
```
Expected: todos pasan (notify_incident no se llama en tests existentes de callback porque usan tipo != INCIDENCIA o no llegan a confirm)

- [ ] **Step 3: Commit**

```bash
git add handlers/callback_handler.py
git commit -m "feat: trigger notify_incident on confirm for INCIDENCIA type"
```

---

## Task 7: command_handler.py — comando /notificaciones

**Files:**
- Modify: `handlers/command_handler.py`

- [ ] **Step 1: Añadir handle_notificaciones al final de command_handler.py**

```python
from storage import get_debug_mode, set_debug_mode, get_notification_preferences, set_notification_mode, toggle_excluded_department
from permissions import get_role


async def handle_notificaciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    employees = context.bot_data.get("employees", {})
    role = get_role(tid, employees)

    if role != "GERENTE_GENERAL":
        await update.message.reply_text("Este comando es solo para el gerente general.")
        return

    args = context.args or []

    if not args:
        prefs = get_notification_preferences(tid)
        mode = prefs["mode"]
        excluded = prefs["excluded_departments"]
        excluded_str = ", ".join(excluded) if excluded else "ninguno"
        await update.message.reply_text(
            f"🔔 <b>Configuración de notificaciones</b>\n\n"
            f"Modo actual: <b>{mode}</b>\n"
            f"Departamentos excluidos: {excluded_str}\n\n"
            f"Opciones:\n"
            f"• /notificaciones todo — todas las incidencias\n"
            f"• /notificaciones criticas — solo CRITICA y ALTA (default)\n"
            f"• /notificaciones solo_criticas — solo CRITICA\n"
            f"• /notificaciones nada — sin notificaciones en tiempo real\n"
            f"• /notificaciones depto NOMBRE — excluir/incluir un departamento",
            parse_mode="HTML",
        )
        return

    cmd = args[0].lower()
    valid_modes = {"todo", "criticas", "solo_criticas", "nada"}

    if cmd in valid_modes:
        set_notification_mode(tid, cmd)
        await update.message.reply_text(f"✅ Modo de notificaciones: <b>{cmd}</b>", parse_mode="HTML")
        return

    if cmd == "depto" and len(args) >= 2:
        dept = args[1].upper()
        is_excluded = toggle_excluded_department(tid, dept)
        estado = "excluido ❌" if is_excluded else "incluido ✅"
        await update.message.reply_text(f"Departamento <b>{dept}</b>: {estado}", parse_mode="HTML")
        return

    await update.message.reply_text(
        "Opción no reconocida. Usá /notificaciones para ver las opciones."
    )
```

También actualizar el import al inicio del archivo:
```python
from telegram import Update
from telegram.ext import ContextTypes
from storage import get_debug_mode, set_debug_mode, get_notification_preferences, set_notification_mode, toggle_excluded_department
from permissions import get_role
```

- [ ] **Step 2: Verificar que importa sin errores**

```bash
cd /home/jaime/hotel-bot-mvp && python3 -c "from handlers.command_handler import handle_notificaciones; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Ejecutar suite completa**

```bash
cd /home/jaime/hotel-bot-mvp && python3 -m pytest tests/ -v --tb=short
```
Expected: todos pasan

- [ ] **Step 4: Commit**

```bash
git add handlers/command_handler.py
git commit -m "feat: /notificaciones command for gerente_general with mode and dept filters"
```

---

## Task 8: bot.py — registrar handler + lessons.md

**Files:**
- Modify: `bot.py`
- Modify: `tasks/lessons.md`

- [ ] **Step 1: Registrar CommandHandler en bot.py**

Cambio quirúrgico: añadir import y handler.

Al inicio, después de `from handlers.command_handler import handle_debug`, añadir:
```python
from handlers.command_handler import handle_debug, handle_notificaciones
```

En `main()`, después de `app.add_handler(CommandHandler("debug", handle_debug))`:
```python
    app.add_handler(CommandHandler("notificaciones", handle_notificaciones))
```

- [ ] **Step 2: Verificar que bot.py importa sin errores**

```bash
cd /home/jaime/hotel-bot-mvp && python3 -c "import bot; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Actualizar tasks/lessons.md**

Añadir sección al final de `tasks/lessons.md`:

```markdown
## Sprint B.2 — Notificaciones (2026-05-15)

### Patrón de redirección por entorno (no por usuario)
`NOTIFICATION_REDIRECT_MODE=admin` redirige todas las notificaciones al admin. Es una decisión de entorno (testing vs producción), no de usuario. El modo se lee en cada `notify_incident()` desde `config/settings`, por lo que cambiar la variable de entorno y reiniciar el bot es suficiente para cambiar de modo.

### Filtros por rol — gerente sí, encargado no
Los filtros de notificación (modo, departamentos excluidos) solo aplican a GERENTE_GENERAL. Los encargados reciben todo lo de su departamento sin filtros. Esto es una regla de diseño deliberada: el encargado necesita ver todo lo de su área para operar; el gerente puede ajustar la señal/ruido según su estilo de gestión.

### La regla "CRITICA siempre llega" como excepción a todos los filtros
Antes de aplicar cualquier filtro (modo, departamentos excluidos), se verifica si `prioridad == "CRITICA"`. Si es así, el gerente recibe la notificación sin importar nada más. Esto se implementa como la primera condición en `_should_notify_gerente()`. La idea: los filtros controlan comodidad, no seguridad operacional.

### save() devuelve lastrowid para conectar notificaciones a incidencias
Antes, `save()` retornaba None. Ahora retorna `cur.lastrowid`. Este ID se usa para registrar en tabla `notifications` qué incidencia disparó qué notificaciones, permitiendo auditoría posterior en SQLite.
```

- [ ] **Step 4: Ejecutar suite final completa**

```bash
cd /home/jaime/hotel-bot-mvp && python3 -m pytest tests/ -v --tb=short
```
Expected: todos pasan

- [ ] **Step 5: Commit final**

```bash
git add bot.py tasks/lessons.md
git commit -m "feat: register /notificaciones handler, update lessons"
```

---

## Para después (NO implementar en B.2)

- Botones inline en notificaciones (Tomar / En proceso / Cerrar) → B.3
- Comandos de consulta `/abiertas`, `/hab N` → B.4
- Notificaciones de GUEST_INTEL, OBSERVACION, NO_REPORTE
- Recordatorios y escalado por timer
- Sincronización a Google Sheets
- Tests automáticos del comando `/notificaciones` (hoy se verifica manual)

---

## Checklist de criterio de éxito

- [ ] `pytest tests/test_notifier.py` → 14 tests PASSED (12 del spec + 2 extras de generate_display_id)
- [ ] `pytest tests/` → todos pasan (sin regresiones en sprints anteriores)
- [ ] Test manual: una incidencia confirmada genera 2 mensajes extra en Telegram del admin con prefijo 🧪
- [ ] Test manual: una OBSERVACION confirmada NO genera mensajes extra
- [ ] Test manual: `/notificaciones` como EMPLEADO → "solo para gerente"
- [ ] Test manual: `/notificaciones` con telegram_id puesto como GERENTE_GENERAL → muestra config
- [ ] Test manual: `/notificaciones nada` + incidencia MEDIA → sin mensaje de gerente
- [ ] Test manual: `/notificaciones nada` + incidencia CRITICA → SÍ llega mensaje de gerente
- [ ] `data/hotel_bot.db` tabla `notifications` tiene registros de cada intento
