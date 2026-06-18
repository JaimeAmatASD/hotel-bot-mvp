import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent))

import storage

EMPLOYEES = {
    222222222: {"telegram_id": 222222222, "nombre": "Andrei", "departamento": "MANTENIMIENTO", "rol": "EMPLEADO"},
    444444444: {"telegram_id": 444444444, "nombre": "Carlos", "departamento": "MANTENIMIENTO", "rol": "ENCARGADO"},
    777777777: {"telegram_id": 777777777, "nombre": "Alfredo", "departamento": "GENERAL", "rol": "GERENTE_GENERAL"},
}


def _seed(con, estado="NUEVA"):
    cur = con.execute(
        """INSERT INTO classifications
           (timestamp, employee_name, employee_dept, message, tipo, prioridad,
            categoria, ubicacion, descripcion, estado)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (datetime.now().isoformat(timespec="seconds"), "Jaime A", "MANTENIMIENTO",
         "x", "INCIDENCIA", "ALTA", "MANTENIMIENTO", "Hab 77", "ventilador roto", estado),
    )
    return cur.lastrowid


def _ctx():
    context = MagicMock()
    context.bot_data = {"employees": EMPLOYEES}
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    return context


def _query(data, from_id):
    q = MagicMock()
    q.from_user.id = from_id
    q.data = data
    q.answer = AsyncMock()
    q.edit_message_reply_markup = AsyncMock()
    q.edit_message_text = AsyncMock()
    q.edit_message_caption = AsyncMock()
    q.message.photo = None
    return q


@pytest.mark.asyncio
async def test_encargado_asigna_a_andrei(tmp_path):
    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        storage.init_db()
        with storage._conn() as con:
            iid = _seed(con)
        from handlers.callback_handler import _handle_incident_action
        # 1) Encargado pulsa "Asignar" → se muestra el picker, no transiciona
        q = _query(f"incident_action:{iid}:asignar", 444444444)
        with patch("handlers.callback_handler.notifier"), \
             patch("handlers.callback_handler.sheets_sync"):
            await _handle_incident_action(q, _ctx())
        q.edit_message_reply_markup.assert_awaited()
        assert storage.get_incident(iid)["estado"] == "NUEVA"

        # 2) Encargado elige a Andrei → ASIGNADA a 222222222
        from handlers.callback_handler import _handle_assign_to
        q2 = _query(f"assign_to:{iid}:222222222", 444444444)
        with patch("handlers.callback_handler.notifier") as nz, \
             patch("handlers.callback_handler.sheets_sync") as sz:
            nz.format_notification_message.return_value = ("msg", None)
            nz.notify_assignee = AsyncMock()
            sz.sync_incidencia = AsyncMock()
            await _handle_assign_to(q2, _ctx())
        inc = storage.get_incident(iid)
        assert inc["estado"] == "ASIGNADA"
        assert int(inc["assigned_to_telegram_id"]) == 222222222


@pytest.mark.asyncio
async def test_empleado_asignado_puede_comenzar(tmp_path):
    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        storage.init_db()
        with storage._conn() as con:
            iid = _seed(con, estado="ASIGNADA")
            con.execute("UPDATE classifications SET assigned_to_telegram_id=222222222 WHERE id=?", (iid,))
        from handlers.callback_handler import _handle_incident_action
        q = _query(f"incident_action:{iid}:comenzar", 222222222)
        with patch("handlers.callback_handler.notifier") as nz, \
             patch("handlers.callback_handler.sheets_sync") as sz:
            nz.format_notification_message.return_value = ("msg", None)
            nz.notify_employee_state_change = AsyncMock()
            nz.notify_managers_resolved = AsyncMock()
            sz.sync_incidencia = AsyncMock()
            await _handle_incident_action(q, _ctx())
        assert storage.get_incident(iid)["estado"] == "EN_PROCESO"


@pytest.mark.asyncio
async def test_empleado_no_asignado_no_puede_comenzar(tmp_path):
    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        storage.init_db()
        with storage._conn() as con:
            iid = _seed(con, estado="ASIGNADA")
            con.execute("UPDATE classifications SET assigned_to_telegram_id=999 WHERE id=?", (iid,))
        from handlers.callback_handler import _handle_incident_action
        q = _query(f"incident_action:{iid}:comenzar", 222222222)
        await _handle_incident_action(q, _ctx())
        q.answer.assert_awaited()
        assert "permiso" in q.answer.call_args[0][0].lower()
        assert storage.get_incident(iid)["estado"] == "ASIGNADA"
