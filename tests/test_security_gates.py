"""Gates de seguridad: usuarios no registrados y validación de asignaciones.

Cubre los fixes de la revisión pre-piloto:
- Comandos de consulta rechazan a usuarios que no están en employees.json.
- can_see_incident identifica al reporter por telegram_id (fallback por nombre).
- assign_to/assign_dept validan destinatario y alcance de departamento.
"""
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import storage
from permissions import can_see_incident

EMPLOYEES = {
    1001: {"telegram_id": 1001, "nombre": "Ana García", "departamento": "SPA", "idioma": "es", "rol": "EMPLEADO"},
    1002: {"telegram_id": 1002, "nombre": "Ana García", "departamento": "HOUSEKEEPING", "idioma": "es", "rol": "EMPLEADO"},
    2001: {"telegram_id": 2001, "nombre": "Carlos Enc", "departamento": "MANTENIMIENTO", "idioma": "es", "rol": "ENCARGADO"},
    3001: {"telegram_id": 3001, "nombre": "Alfredo Gte", "departamento": "GENERAL", "idioma": "es", "rol": "GERENTE_GENERAL"},
    4001: {"telegram_id": 4001, "nombre": "Sofía Recep", "departamento": "RECEPCION", "idioma": "es", "rol": "EMPLEADO"},
}

UNREGISTERED_TID = 666


def _update(user_id):
    update = MagicMock()
    update.message = AsyncMock()
    update.effective_user = MagicMock(id=user_id)
    return update


def _ctx(args=None):
    ctx = MagicMock()
    ctx.bot_data = {"employees": EMPLOYEES}
    ctx.args = args or []
    return ctx


def _seed_incident(con, estado="NUEVA", employee_telegram_id=1001, employee_name="Ana García"):
    cur = con.execute(
        """INSERT INTO classifications
           (timestamp, employee_name, employee_dept, employee_telegram_id, message,
            tipo, prioridad, categoria, ubicacion, descripcion, estado)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (datetime.now().isoformat(timespec="seconds"), employee_name, "SPA",
         employee_telegram_id, "x", "INCIDENCIA", "ALTA", "MANTENIMIENTO",
         "Hab 204", "goteo aire", estado),
    )
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Comandos: no registrado → rechazado sin filtrar datos
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("args", [["204"]])
async def test_hab_rechaza_no_registrado(tmp_path, args):
    from handlers.command_handler import handle_hab
    update = _update(UNREGISTERED_TID)
    await handle_hab(update, _ctx(args))
    reply = update.message.reply_text.call_args[0][0]
    assert "registrado" in reply.lower()


@pytest.mark.asyncio
async def test_buscar_rechaza_no_registrado(tmp_path):
    from handlers.command_handler import handle_buscar
    update = _update(UNREGISTERED_TID)
    await handle_buscar(update, _ctx(["goteo"]))
    reply = update.message.reply_text.call_args[0][0]
    assert "registrado" in reply.lower()


@pytest.mark.asyncio
async def test_historial_rechaza_no_registrado(tmp_path):
    from handlers.command_handler import handle_historial
    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        storage.init_db()
        with storage._conn() as con:
            iid = _seed_incident(con)
        update = _update(UNREGISTERED_TID)
        await handle_historial(update, _ctx([str(iid)]))
        reply = update.message.reply_text.call_args[0][0]
        assert "registrado" in reply.lower()
        assert "goteo" not in reply.lower()


@pytest.mark.asyncio
async def test_reporte_rep_n_rechaza_no_registrado(tmp_path):
    from handlers.command_handler import handle_reporte
    update = _update(UNREGISTERED_TID)
    await handle_reporte(update, _ctx(["REP-1"]))
    reply = update.message.reply_text.call_args[0][0]
    assert "registrado" in reply.lower()


# ---------------------------------------------------------------------------
# Identidad del reporter por telegram_id
# ---------------------------------------------------------------------------

def test_reporter_ve_su_incidencia_por_telegram_id():
    inc = {"categoria": "MANTENIMIENTO", "employee_name": "Ana García", "employee_telegram_id": 1001}
    assert can_see_incident(EMPLOYEES[1001], inc) is True


def test_homonimo_no_ve_incidencia_ajena():
    """Dos 'Ana García': la de HOUSEKEEPING no debe ver lo que reportó la del SPA."""
    inc = {"categoria": "MANTENIMIENTO", "employee_name": "Ana García", "employee_telegram_id": 1001}
    assert can_see_incident(EMPLOYEES[1002], inc) is False


def test_fila_legacy_sin_telegram_id_usa_nombre():
    inc = {"categoria": "MANTENIMIENTO", "employee_name": "Ana García"}
    assert can_see_incident(EMPLOYEES[1001], inc) is True


def test_save_persiste_employee_telegram_id(tmp_path):
    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        storage.init_db()
        result = {"tipo": "INCIDENCIA", "prioridad": "ALTA", "categoria": "MANTENIMIENTO",
                  "ubicacion": "Hab 204", "descripcion": "goteo", "confianza": 0.9}
        iid = storage.save(EMPLOYEES[1001], "hay un goteo", result)
        inc = storage.get_incident(iid)
        assert inc["employee_telegram_id"] == 1001


# ---------------------------------------------------------------------------
# Validación de asignaciones (callback_data no es confiable)
# ---------------------------------------------------------------------------

def _query(data, from_id):
    q = MagicMock()
    q.from_user.id = from_id
    q.data = data
    q.answer = AsyncMock()
    q.edit_message_reply_markup = AsyncMock()
    q.edit_message_text = AsyncMock()
    q.message.photo = None
    return q


def _cb_ctx():
    ctx = MagicMock()
    ctx.bot_data = {"employees": EMPLOYEES}
    ctx.bot = MagicMock()
    return ctx


@pytest.mark.asyncio
async def test_assign_to_rechaza_destinatario_desconocido(tmp_path):
    from handlers.callback_handler import _handle_assign_to
    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        storage.init_db()
        with storage._conn() as con:
            iid = _seed_incident(con)
        q = _query(f"assign_to:{iid}:999999", 2001)  # encargado MANT, target inexistente
        await _handle_assign_to(q, _cb_ctx())
        assert "inválido" in q.answer.call_args[0][0].lower()
        assert storage.get_incident(iid)["estado"] == "NUEVA"


@pytest.mark.asyncio
async def test_encargado_no_asigna_fuera_de_su_departamento(tmp_path):
    from handlers.callback_handler import _handle_assign_to
    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        storage.init_db()
        with storage._conn() as con:
            iid = _seed_incident(con)  # categoría MANTENIMIENTO
        # Encargado de MANTENIMIENTO intenta asignar a Sofía (RECEPCION) con callback crafteado
        q = _query(f"assign_to:{iid}:4001", 2001)
        await _handle_assign_to(q, _cb_ctx())
        assert "departamento" in q.answer.call_args[0][0].lower()
        assert storage.get_incident(iid)["estado"] == "NUEVA"


@pytest.mark.asyncio
async def test_gerente_si_puede_asignar_cross_departamento(tmp_path):
    from handlers.callback_handler import _handle_assign_to
    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        storage.init_db()
        with storage._conn() as con:
            iid = _seed_incident(con)
        q = _query(f"assign_to:{iid}:4001", 3001)  # gerente asigna a RECEPCION
        with patch("handlers.callback_handler.notifier") as nz, \
             patch("handlers.callback_handler.sheets_sync") as sz:
            nz.format_notification_message.return_value = ("msg", None)
            nz.notify_assignee = AsyncMock()
            sz.sync_incidencia = AsyncMock()
            await _handle_assign_to(q, _cb_ctx())
        inc = storage.get_incident(iid)
        assert inc["estado"] == "ASIGNADA"
        assert int(inc["assigned_to_telegram_id"]) == 4001


@pytest.mark.asyncio
async def test_assign_to_callback_malformado_no_explota(tmp_path):
    from handlers.callback_handler import _handle_assign_to
    q = _query("assign_to:abc", 2001)
    await _handle_assign_to(q, _cb_ctx())
    assert "inválido" in q.answer.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_assign_dept_encargado_no_abre_otro_depto(tmp_path):
    from handlers.callback_handler import _handle_assign_dept
    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        storage.init_db()
        with storage._conn() as con:
            iid = _seed_incident(con)  # MANTENIMIENTO
        q = _query(f"assign_dept:{iid}:RECEPCION", 2001)
        await _handle_assign_dept(q, _cb_ctx())
        assert "departamento" in q.answer.call_args[0][0].lower()
        q.edit_message_reply_markup.assert_not_awaited()
