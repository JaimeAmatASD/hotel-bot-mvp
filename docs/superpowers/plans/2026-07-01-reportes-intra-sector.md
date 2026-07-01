# Reportes intra-sector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Acotar el informe de turno al piloto de un solo sector (bot → encargado, gerencia/dueños vía Sheets) y agregar un rollup de sector read-only on-demand.

**Architecture:** El aviso al gerente general en el informe de turno queda detrás de un flag de config reversible (`REPORT_NOTIFY_GERENTE`, default off). Se agrega `/reporte sector [depto] [ventana]`: una vista de solo lectura que combina incidencias + novedades + notas de huésped del sector en una ventana, reutilizando la plantilla existente vía una función de secciones extraída. No crea REPs ni toca la DB.

**Tech Stack:** Python 3.11, python-telegram-bot v20+, SQLite (`storage/`), pytest/unittest.

## Global Constraints

- Alcance: solo tipos `INCIDENCIA`, `OBSERVACION`, `GUEST_INTEL`; el rollup es **read-only** (no crea `reports`, no toca `report_id`/`estado`).
- Magic strings prohibidos: usar `config.enums` (`ReportType`, `Role`, `IncidentState`).
- El piloto de un solo sector se define por `employees.json` (deployment), **no** por código.
- Depto de un ítem: para `INCIDENCIA` = `permissions._incident_department(item)`; para `OBSERVACION`/`GUEST_INTEL` = `item["employee_dept"]`.
- Tests: `venv/bin/pytest -q` debe quedar verde (hoy 223 passed).

---

## File Structure

- `config/settings.py` — **Modify**: nuevo flag `REPORT_NOTIFY_GERENTE`.
- `report_processor.py` — **Modify**: gate del gerente en `notify_manager_report`; extracción `_render_item_sections`; nuevas `sector_items` y `render_sector_rollup`.
- `storage/reports.py` — **Modify**: nueva `get_classifications_recent`.
- `storage/__init__.py` — **Modify**: exportar `get_classifications_recent`.
- `handlers/command_handler.py` — **Modify**: rama `/reporte sector` en `handle_reporte`.
- `presenters/help_text.py` — **Modify**: documentar `/reporte sector`.
- `tests/test_reports.py` — **Modify**: actualizar test del gerente; nuevos tests de flag, query, rollup.
- `tests/test_shift_report_template.py` — **Test** (sin cambios; debe seguir verde tras el refactor).
- `tests/test_hotel_scenarios.py` — **Modify**: E2E del rollup + gerente no notificado.

---

## Task 1: Flag de config + gate del gerente en el informe de turno

**Files:**
- Modify: `config/settings.py`
- Modify: `report_processor.py:148-179` (`notify_manager_report`)
- Test: `tests/test_reports.py`

**Interfaces:**
- Produces: `config.settings.REPORT_NOTIFY_GERENTE: bool` (default `False`).
- Consumes: `report_processor.notify_manager_report(bot, report, items, employees)` (firma sin cambios).

- [ ] **Step 1: Escribir el test que falla**

En `tests/test_reports.py`, dentro de `class TestConfirmReport(Base)`, agregar:

```python
    def test_gerente_gated_by_flag_off(self):
        items = self._make_items()  # EMPLOYEE es de SPA
        rid = storage.create_report(self.EMPLOYEE)
        storage.link_classifications_to_report([i["id"] for i in items], rid)
        rep = storage.get_report_with_items(rid)

        enc_spa = {"telegram_id": 5555, "nombre": "Sole Enc SPA",
                   "departamento": "SPA", "rol": "ENCARGADO"}
        employees = {
            self.EMPLOYEE["telegram_id"]: self.EMPLOYEE,
            enc_spa["telegram_id"]: enc_spa,
            self.GERENTE["telegram_id"]: self.GERENTE,
        }
        storage.set_notification_mode(self.GERENTE["telegram_id"], "todo")  # querría recibir

        bot = MagicMock()
        bot.send_message = AsyncMock()
        with patch("report_processor.settings.REPORT_NOTIFY_GERENTE", False):
            asyncio.run(report_processor.notify_manager_report(bot, rep, items, employees))

        sent_to = [c.kwargs.get("chat_id") for c in bot.send_message.call_args_list]
        self.assertIn(5555, sent_to)                              # encargado del depto: sí
        self.assertNotIn(self.GERENTE["telegram_id"], sent_to)    # gerente: NO (flag off)
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `venv/bin/pytest tests/test_reports.py::TestConfirmReport::test_gerente_gated_by_flag_off -v`
Expected: FAIL — el gerente recibe (aún no existe el flag/gate).

- [ ] **Step 3: Agregar el flag en `config/settings.py`**

Agregar (junto a los otros `os.environ.get`):

```python
REPORT_NOTIFY_GERENTE = os.environ.get("REPORT_NOTIFY_GERENTE", "false").lower() == "true"
```

- [ ] **Step 4: Gate del gerente en `report_processor.notify_manager_report`**

En `report_processor.py`, dentro del `for tid, emp in employees.items()`, cambiar la rama del gerente general para que respete el flag:

```python
        elif rol == Role.GERENTE_GENERAL:
            if not settings.REPORT_NOTIFY_GERENTE:
                continue
            if storage.get_notification_preferences(tid).get("mode") != NotificationMode.TODO:
                continue
```

(`from config import settings` ya está importado en `report_processor.py`.)

- [ ] **Step 5: Actualizar el test existente que asumía gerente notificado**

En `tests/test_reports.py::TestConfirmReport::test_notify_manager_only_mode_todo`, envolver la llamada con el flag en `True`:

```python
        bot = MagicMock()
        bot.send_message = AsyncMock()

        with patch("report_processor.settings.REPORT_NOTIFY_GERENTE", True):
            asyncio.run(report_processor.notify_manager_report(bot, rep, items, employees))
        bot.send_message.assert_called_once()
```

- [ ] **Step 6: Correr los tests del módulo**

Run: `venv/bin/pytest tests/test_reports.py -q`
Expected: PASS (incluye el nuevo test y el actualizado).

- [ ] **Step 7: Commit**

```bash
git add config/settings.py report_processor.py tests/test_reports.py
git commit -m "feat(reporte): gate aviso al gerente detrás de REPORT_NOTIFY_GERENTE (piloto intra-sector)"
```

---

## Task 2: Query de storage — ítems del sistema en una ventana

**Files:**
- Modify: `storage/reports.py` (junto a `get_classifications_for_employee_recent:55`)
- Modify: `storage/__init__.py:37-65`
- Test: `tests/test_reports.py`

**Interfaces:**
- Produces: `storage.get_classifications_recent(hours: int) -> list[dict]` — todas las clasificaciones en las últimas N horas (excluye `NO_REPORTE`/`ERROR`), de cualquier empleado, sin filtrar por `report_id`. Orden `timestamp ASC`.

- [ ] **Step 1: Escribir el test que falla**

En `tests/test_reports.py`, dentro de `class TestStorageNew(Base)`, agregar:

```python
    def test_get_classifications_recent_all_employees_incl_reported(self):
        _insert_classification(str(self.db_path), "Ana", "INCIDENCIA", "inc1")
        _insert_classification(str(self.db_path), "Beto", "OBSERVACION", "obs1", report_id=99)  # ya en REP
        _insert_classification(str(self.db_path), "Ana", "NO_REPORTE", "chau")                  # excluido
        _insert_classification(str(self.db_path), "Ana", "INCIDENCIA", "viejo", hours_ago=48)   # fuera ventana

        rows = storage.get_classifications_recent(24)
        descs = [r["descripcion"] for r in rows]
        self.assertIn("inc1", descs)
        self.assertIn("obs1", descs)          # incluye ya-consolidados
        self.assertNotIn("chau", descs)       # excluye NO_REPORTE
        self.assertNotIn("viejo", descs)      # excluye fuera de ventana
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `venv/bin/pytest tests/test_reports.py::TestStorageNew::test_get_classifications_recent_all_employees_incl_reported -v`
Expected: FAIL — `AttributeError: module 'storage' has no attribute 'get_classifications_recent'`.

- [ ] **Step 3: Implementar la query en `storage/reports.py`**

Agregar (después de `get_classifications_for_employee_recent`). Reutiliza `datetime`/`timedelta`/`_conn` ya importados en el módulo:

```python
def get_classifications_recent(hours: int) -> list[dict]:
    """Todas las clasificaciones en las últimas N horas (excluye NO_REPORTE/ERROR),
    de cualquier empleado y sin importar si ya están en un reporte. Solo lectura."""
    since = (datetime.now() - timedelta(hours=hours)).isoformat(timespec="seconds")
    with _conn() as con:
        rows = con.execute(
            """SELECT * FROM classifications
               WHERE timestamp >= ?
                 AND tipo NOT IN ('NO_REPORTE', 'ERROR')
               ORDER BY timestamp ASC""",
            (since,),
        ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Exportar en `storage/__init__.py`**

En el bloque `from storage.reports import (` agregar `get_classifications_recent,` y en `__all__` agregar `"get_classifications_recent",` junto a `"get_classifications_for_employee_recent"`.

- [ ] **Step 5: Correr el test para verificar que pasa**

Run: `venv/bin/pytest tests/test_reports.py::TestStorageNew::test_get_classifications_recent_all_employees_incl_reported -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add storage/reports.py storage/__init__.py tests/test_reports.py
git commit -m "feat(storage): get_classifications_recent (ventana del sistema, read-only)"
```

---

## Task 3: report_processor — secciones compartidas, filtro de sector y rollup

**Files:**
- Modify: `report_processor.py` (extracción + funciones nuevas; `render_shift_report:29-92`)
- Test: `tests/test_reports.py`, `tests/test_shift_report_template.py` (debe seguir verde)

**Interfaces:**
- Consumes: `storage.get_classifications_recent(hours)` (Task 2); `permissions._incident_department(item) -> str`.
- Produces:
  - `report_processor.sector_items(department: str, hours: int) -> list[dict]`
  - `report_processor.render_sector_rollup(items: list[dict], *, department: str, hours: int) -> str`
  - `report_processor._render_item_sections(items: list[dict]) -> tuple[list[str], list[dict]]` (helper, devuelve líneas de secciones numeradas + incidencias abiertas).

- [ ] **Step 1: Escribir los tests que fallan**

En `tests/test_reports.py`, agregar una clase nueva al final:

```python
class TestSectorRollup(Base):
    def test_sector_items_filters_by_department(self):
        # Incidencia de MANTENIMIENTO (por categoría) reportada por alguien de SPA
        import sqlite3
        from datetime import datetime
        ts = datetime.now().isoformat(timespec="seconds")
        with sqlite3.connect(str(self.db_path)) as con:
            con.execute(
                """INSERT INTO classifications
                   (timestamp, employee_name, employee_dept, message, tipo, prioridad,
                    categoria, ubicacion, descripcion, confianza, campos_faltantes, report_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (ts, "Jaime A", "SPA", "m", "INCIDENCIA", "ALTA",
                 "MANTENIMIENTO", "Hab 8", "baño roto", 0.9, "[]", None),
            )
        # Observación de un empleado de SPA → depto = SPA (employee_dept)
        _insert_classification(str(self.db_path), "Sole", "OBSERVACION", "ronda spa")  # employee_dept=SPA

        mant = report_processor.sector_items("MANTENIMIENTO", 24)
        spa = report_processor.sector_items("SPA", 24)
        self.assertEqual([i["descripcion"] for i in mant], ["baño roto"])
        self.assertEqual([i["descripcion"] for i in spa], ["ronda spa"])

    def test_render_sector_rollup_header_and_no_footer(self):
        items = [
            {"tipo": "INCIDENCIA", "estado": "NUEVA", "prioridad": "ALTA",
             "ubicacion": "Hab 8", "descripcion": "baño roto",
             "timestamp": "2026-07-01T08:00:00"},
            {"tipo": "OBSERVACION", "descripcion": "ronda ok",
             "timestamp": "2026-07-01T09:00:00"},
        ]
        text = report_processor.render_sector_rollup(items, department="MANTENIMIENTO", hours=24)
        self.assertIn("ESTADO DEL SECTOR — MANTENIMIENTO", text)
        self.assertIn("últimas 24h", text)
        self.assertIn("ABIERTAS EN EL SECTOR", text)   # la incidencia NUEVA aparece
        self.assertNotIn("Cerrado", text)              # no es un REP
        self.assertNotIn("INFORME DE TURNO", text)
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `venv/bin/pytest tests/test_reports.py::TestSectorRollup -v`
Expected: FAIL — `sector_items`/`render_sector_rollup` no existen.

- [ ] **Step 3: Extraer `_render_item_sections` en `report_processor.py`**

Agregar el helper (antes de `render_shift_report`), copiando la lógica de numeración/secciones que hoy vive inline:

```python
def _render_item_sections(items: list[dict]) -> tuple[list[str], list[dict]]:
    """Devuelve (líneas de secciones numeradas, incidencias abiertas). Compartido
    por el informe per-persona y el rollup de sector."""
    incidencias = [i for i in items if i.get("tipo") == ReportType.INCIDENCIA]
    guest = [i for i in items if i.get("tipo") == ReportType.GUEST_INTEL]
    obs = [i for i in items if i.get("tipo") == ReportType.OBSERVACION]

    lines: list[str] = []
    num = 1
    if incidencias:
        lines.append(f"🔧 INCIDENCIAS ({len(incidencias)})")
        for it in incidencias:
            estado = it.get("estado") or IncidentState.NUEVA
            em = ESTADO_EMOJI.get(estado, "")
            ubic = it.get("ubicacion", "") or ""
            desc = it.get("descripcion", "") or ""
            prio = it.get("prioridad", "") or ""
            lines.append(f" {num}. {ubic} — {desc} · {prio} · {em} {estado}".replace("  ", " "))
            num += 1
    if guest:
        lines.append(f"👤 NOTAS DE HUÉSPED ({len(guest)})")
        for it in guest:
            ubic = it.get("ubicacion", "") or ""
            desc = it.get("descripcion", "") or ""
            prefix = f"{ubic} — " if ubic else ""
            lines.append(f" {num}. {prefix}{desc}")
            num += 1
    if obs:
        lines.append(f"📝 NOVEDADES DEL TURNO ({len(obs)})")
        for it in obs:
            lines.append(f" {num}. {it.get('descripcion', '') or ''}")
            num += 1

    pendientes = [i for i in incidencias
                  if (i.get("estado") or IncidentState.NUEVA) not in _TERMINAL_STATES]
    return lines, pendientes
```

- [ ] **Step 4: Reescribir `render_shift_report` para usar el helper (mismo output)**

Reemplazar el cuerpo desde `num = 1` (línea ~48) hasta el cálculo de `pendientes` por:

```python
    section_lines, pendientes = _render_item_sections(items)
    lines.extend(section_lines)

    if pendientes:
        lines.append("⏳ QUEDA PENDIENTE PARA EL PRÓXIMO TURNO")
        for it in pendientes:
            ubic = it.get("ubicacion", "") or ""
            desc = it.get("descripcion", "") or ""
            estado = it.get("estado") or IncidentState.NUEVA
            lines.append(f" • {ubic} — {desc} ({estado})")
```

(El resto de `render_shift_report` —cabecera, `_DIVIDER`, footer `closed_at`— queda igual.)

- [ ] **Step 5: Verificar que la plantilla existente no cambió**

Run: `venv/bin/pytest tests/test_shift_report_template.py -q`
Expected: PASS (los 3 tests de plantilla siguen verdes — el refactor preserva el output).

- [ ] **Step 6: Implementar `sector_items` y `render_sector_rollup`**

Agregar `import permissions` al tope de `report_processor.py` (no crea ciclo: `permissions` no importa `report_processor`). Luego:

```python
def sector_items(department: str, hours: int) -> list[dict]:
    """Ítems del sector en la ventana (read-only). Incidencias por categoría→depto;
    observaciones/notas de huésped por el depto del que reportó."""
    dept = department.upper()
    out = []
    for it in storage.get_classifications_recent(hours):
        if it.get("tipo") == ReportType.INCIDENCIA:
            item_dept = permissions._incident_department(it)
        else:
            item_dept = it.get("employee_dept") or ""
        if item_dept.upper() == dept:
            out.append(it)
    return out


def render_sector_rollup(items: list[dict], *, department: str, hours: int) -> str:
    """Vista read-only del estado del sector en la ventana. No es un REP."""
    total = len(items)
    rng = _time_range(items)
    meta = f"{rng} · " if rng else ""
    lines = [
        f"📋 ESTADO DEL SECTOR — {department}",
        f"🕐 {meta}{total} ítem{'s' if total != 1 else ''} · últimas {hours}h",
        _DIVIDER,
    ]
    section_lines, abiertas = _render_item_sections(items)
    if not section_lines:
        lines.append("Sin actividad en la ventana.")
    lines.extend(section_lines)
    if abiertas:
        lines.append("⏳ ABIERTAS EN EL SECTOR")
        for it in abiertas:
            ubic = it.get("ubicacion", "") or ""
            desc = it.get("descripcion", "") or ""
            estado = it.get("estado") or IncidentState.NUEVA
            lines.append(f" • {ubic} — {desc} ({estado})")
    lines.append(_DIVIDER)
    return "\n".join(lines)
```

- [ ] **Step 7: Correr los tests para verificar que pasan**

Run: `venv/bin/pytest tests/test_reports.py::TestSectorRollup tests/test_shift_report_template.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add report_processor.py tests/test_reports.py
git commit -m "feat(reporte): rollup de sector read-only + secciones compartidas"
```

---

## Task 4: Handler `/reporte sector` + permisos + /help

**Files:**
- Modify: `handlers/command_handler.py:247` (`handle_reporte`)
- Modify: `presenters/help_text.py`
- Test: `tests/test_reports.py`

**Interfaces:**
- Consumes: `report_processor.sector_items`, `report_processor.render_sector_rollup` (Task 3); `permissions.is_manager(tid, employees) -> bool`; `permissions.can_query_department(user, dept) -> bool`.

- [ ] **Step 1: Escribir el test que falla**

En `tests/test_reports.py`, agregar al final (usa el handler directo con mocks de Telegram):

```python
class TestReporteSectorCommand(Base):
    def _ctx(self, user, employees, args):
        ctx = MagicMock()
        ctx.args = args
        ctx.bot_data = {"employees": employees}
        ctx.user_data = {}
        return ctx

    def _update(self, tid):
        upd = MagicMock()
        upd.effective_user.id = tid
        upd.message.reply_text = AsyncMock()
        return upd

    def test_empleado_rechazado(self):
        from handlers.command_handler import handle_reporte
        emp = {"telegram_id": 1, "nombre": "Emp", "departamento": "SPA", "rol": "EMPLEADO"}
        upd = self._update(1)
        ctx = self._ctx(emp, {1: emp}, ["sector"])
        asyncio.run(handle_reporte(upd, ctx))
        msg = upd.message.reply_text.call_args.args[0]
        self.assertIn("encargados", msg.lower())

    def test_encargado_ve_su_sector(self):
        from handlers.command_handler import handle_reporte
        _insert_classification(str(self.db_path), "Sole", "OBSERVACION", "ronda spa")  # employee_dept=SPA
        enc = {"telegram_id": 2, "nombre": "Enc SPA", "departamento": "SPA", "rol": "ENCARGADO"}
        upd = self._update(2)
        ctx = self._ctx(enc, {2: enc}, ["sector"])
        asyncio.run(handle_reporte(upd, ctx))
        msg = upd.message.reply_text.call_args.args[0]
        self.assertIn("ESTADO DEL SECTOR — SPA", msg)
        self.assertIn("ronda spa", msg)

    def test_encargado_no_puede_otro_sector(self):
        from handlers.command_handler import handle_reporte
        enc = {"telegram_id": 2, "nombre": "Enc SPA", "departamento": "SPA", "rol": "ENCARGADO"}
        upd = self._update(2)
        ctx = self._ctx(enc, {2: enc}, ["sector", "MANTENIMIENTO"])
        asyncio.run(handle_reporte(upd, ctx))
        msg = upd.message.reply_text.call_args.args[0]
        self.assertIn("acceso", msg.lower())
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `venv/bin/pytest tests/test_reports.py::TestReporteSectorCommand -v`
Expected: FAIL — no existe la rama `sector` (cae en el parseo de ventana/REP-N).

- [ ] **Step 3: Agregar la rama `sector` en `handle_reporte`**

En `handlers/command_handler.py`, dentro de `if args:` (justo después de `arg = args[0]`, antes de la rama `\d+h`), insertar:

```python
        if arg.lower() == "sector":
            if not user:
                await update.message.reply_text("❌ No estás registrado.")
                return
            if not permissions.is_manager(tid, employees):
                await update.message.reply_text(
                    "Solo encargados y gerencia pueden ver el estado del sector."
                )
                return
            hours = 24
            department = user.get("departamento")
            for a in args[1:]:
                if re.fullmatch(r"\d+h", a, re.IGNORECASE):
                    hours = int(a[:-1])
                else:
                    department = a.upper()
            if not department or department == "GENERAL":
                await update.message.reply_text(
                    "Indicá el sector: `/reporte sector MANTENIMIENTO`", parse_mode="Markdown"
                )
                return
            if not can_query_department(user, department):
                await update.message.reply_text("No tenés acceso a ese sector.")
                return
            items = report_processor.sector_items(department, hours)
            text = report_processor.render_sector_rollup(items, department=department, hours=hours)
            await update.message.reply_text(text)
            return
```

(`tid`, `user`, `employees`, `args` ya están definidos arriba en la función; `permissions`, `can_query_department`, `report_processor`, `re` ya están importados.)

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run: `venv/bin/pytest tests/test_reports.py::TestReporteSectorCommand -v`
Expected: PASS.

- [ ] **Step 5: Documentar en `/help`**

En `presenters/help_text.py`, en el bloque del `ENCARGADO`, debajo de la línea `/fin — ...`, agregar:

```python
            "\n/reporte sector [6h] — estado del sector en el turno (solo lectura)"
```

Y en el bloque del `GERENTE_GENERAL`, debajo de su línea `/fin — ...`, agregar:

```python
            "\n/reporte sector <depto> [6h] — estado de un sector (solo lectura)"
```

- [ ] **Step 6: Correr la suite completa**

Run: `venv/bin/pytest -q`
Expected: PASS (todo verde).

- [ ] **Step 7: Commit**

```bash
git add handlers/command_handler.py presenters/help_text.py tests/test_reports.py
git commit -m "feat(commands): /reporte sector — rollup read-only del sector (encargado/gerente)"
```

---

## Task 5: E2E — rollup combinado + gerente no notificado

**Files:**
- Modify: `tests/test_hotel_scenarios.py`

**Interfaces:**
- Consumes: `handlers.command_handler.handle_reporte`; `report_processor.notify_manager_report`; helpers de escenario ya existentes (`seed_classification`, `make_message_update`, etc.).

- [ ] **Step 1: Escribir el test E2E que falla**

En `tests/test_hotel_scenarios.py`, agregar un test siguiendo el patrón de los existentes (revisar los helpers reales del archivo — `seed_classification`, `make_message_update`, construcción de `context`). Esqueleto a completar con esos helpers:

```python
@pytest.mark.asyncio
async def test_sector_rollup_combines_types_and_gerente_gated(monkeypatch):
    """Varios ítems del sector → /reporte sector muestra el combinado; con el flag
    off el gerente no recibe el informe per-persona por el bot."""
    from handlers.command_handler import handle_reporte
    import report_processor
    monkeypatch.setattr("report_processor.settings.REPORT_NOTIFY_GERENTE", False)

    # 2 empleados de MANTENIMIENTO cargan incidencia + novedad + nota de huésped
    seed_classification(EMP_MANT, {"tipo": "INCIDENCIA", "prioridad": "ALTA",
        "categoria": "MANTENIMIENTO", "ubicacion": "Hab 8", "descripcion": "baño roto",
        "estado": "NUEVA"})
    seed_classification(EMP_MANT, {"tipo": "OBSERVACION", "ubicacion": "Pisos",
        "descripcion": "ronda sin novedad"})
    seed_classification(EMP_MANT, {"tipo": "GUEST_INTEL", "ubicacion": "Hab 45",
        "descripcion": "huésped pide toallas"})

    # El encargado de MANTENIMIENTO pide el rollup
    upd = make_message_update(ENC_MANT["telegram_id"], "/reporte sector")
    context.args = ["sector"]
    await handle_reporte(upd, context)
    text = latest_reply_text(upd)
    assert "ESTADO DEL SECTOR — MANTENIMIENTO" in text
    assert "baño roto" in text and "ronda sin novedad" in text and "huésped pide toallas" in text
    assert "ABIERTAS EN EL SECTOR" in text  # la incidencia NUEVA
```

Nota para el implementador: usar los fixtures/empleados reales del archivo (`EMP_MANT`/`ENC_MANT` o equivalentes; si no existen con esos nombres, definir dicts locales de rol EMPLEADO/ENCARGADO en MANTENIMIENTO y armar `context.bot_data["employees"]` como en los otros tests). Asegurar que la ventana por defecto (24h) cubra los ítems sembrados.

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `venv/bin/pytest tests/test_hotel_scenarios.py::test_sector_rollup_combines_types_and_gerente_gated -v`
Expected: FAIL primero por ajustes de fixtures; iterar hasta que falle solo por aserción y luego pase con la implementación de Tasks 1-4.

- [ ] **Step 3: Ajustar hasta verde**

Completar helpers/fixtures según el archivo. No se toca código de producción (ya implementado en Tasks 1-4).

- [ ] **Step 4: Correr el test para verificar que pasa**

Run: `venv/bin/pytest tests/test_hotel_scenarios.py::test_sector_rollup_combines_types_and_gerente_gated -v`
Expected: PASS.

- [ ] **Step 5: Suite completa + commit**

Run: `venv/bin/pytest -q`
Expected: PASS.

```bash
git add tests/test_hotel_scenarios.py
git commit -m "test(e2e): rollup de sector combinado + gerente gateado por flag"
```

---

## Self-Review

- **Spec coverage:**
  - Cambio 1 (flag + apagar gerente) → Task 1. ✅
  - Cambio 2 (rollup on-demand): query → Task 2; filtro + render → Task 3; comando + permisos → Task 4. ✅
  - Cambio 3 (Sheets sin código) → nada que implementar. ✅
  - Cambio 4 (/help) → Task 4 Step 5. ✅
  - Testing (flag, permisos, datos/formato, read-only, E2E) → Tasks 1,3,4,5. ✅
    - Read-only queda cubierto porque `sector_items`/`render_sector_rollup` no escriben DB y sus tests no crean `reports`; el E2E lo evidencia.
- **Placeholder scan:** el único punto abierto es Task 5 Step 1 (fixtures reales del archivo de escenarios) — es intencional y acotado a nombres de helpers que el implementador debe leer del archivo; el resto del test es concreto.
- **Type consistency:** `get_classifications_recent(hours)`, `sector_items(department, hours)`, `render_sector_rollup(items, *, department, hours)`, `_render_item_sections(items) -> (lines, abiertas)` usados consistentemente entre Tasks 2-5. `REPORT_NOTIFY_GERENTE` referenciado igual en Tasks 1 y 5.
