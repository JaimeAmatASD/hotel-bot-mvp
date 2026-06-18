"""Tests for Sprint B.3: incident state transitions and action keyboards."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import storage
import permissions
from notifier import build_keyboard_for_state


def _make_db(tmp_path):
    """Point storage at a fresh temp DB and init it."""
    db_path = Path(tmp_path) / "test.db"
    return db_path


def _seed_incident(con, tipo="INCIDENCIA", categoria="Sanitarios", estado="NUEVA"):
    """Insert a minimal incident row and return its id."""
    from datetime import datetime
    cur = con.execute(
        """INSERT INTO classifications
           (timestamp, employee_name, employee_dept, message, tipo, prioridad,
            categoria, ubicacion, descripcion, estado)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            datetime.now().isoformat(timespec="seconds"),
            "Jaime A", "SPA", "test message", tipo, "ALTA",
            categoria, "Habitación 305", "Baño roto en habitación 305", estado,
        ),
    )
    return cur.lastrowid


class TestStorageTransitions(unittest.TestCase):

    ENC = {"telegram_id": 444444444, "nombre": "Carlos Encargado Mant",
           "rol": "ENCARGADO", "departamento": "MANTENIMIENTO"}
    EMP = {"telegram_id": 222222222, "nombre": "Andrei Popescu",
           "rol": "EMPLEADO", "departamento": "MANTENIMIENTO"}

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db"
        self.patcher = patch.object(storage, "DB_PATH", self.db_path)
        self.patcher.start()
        storage.init_db()

    def tearDown(self):
        self.patcher.stop()

    def _seed(self, estado="NUEVA", categoria="MANTENIMIENTO"):
        with storage._conn() as con:
            return _seed_incident(con, categoria=categoria, estado=estado)

    def test_asignar_a_otra_persona(self):
        iid = self._seed("NUEVA")
        r = storage.update_incident_state_atomic(
            iid, "ASIGNADA", self.ENC, ["NUEVA"],
            action="asignar", assignee_telegram_id=222222222)
        self.assertTrue(r["success"])
        inc = storage.get_incident(iid)
        self.assertEqual(inc["estado"], "ASIGNADA")
        self.assertEqual(int(inc["assigned_to_telegram_id"]), 222222222)
        self.assertEqual(int(inc["assigned_by"]), 444444444)

    def test_tomar_para_si(self):
        iid = self._seed("NUEVA")
        storage.update_incident_state_atomic(
            iid, "ASIGNADA", self.ENC, ["NUEVA"], action="tomar")
        inc = storage.get_incident(iid)
        self.assertEqual(int(inc["assigned_to_telegram_id"]), 444444444)

    def test_comenzar_marca_en_proceso(self):
        iid = self._seed("ASIGNADA")
        r = storage.update_incident_state_atomic(
            iid, "EN_PROCESO", self.EMP, ["ASIGNADA"], action="comenzar")
        self.assertTrue(r["success"])
        self.assertEqual(storage.get_incident(iid)["estado"], "EN_PROCESO")

    def test_terminado_guarda_resolved_by(self):
        iid = self._seed("EN_PROCESO")
        r = storage.update_incident_state_atomic(
            iid, "RESUELTA", self.EMP, ["EN_PROCESO"], action="terminado")
        self.assertTrue(r["success"])
        inc = storage.get_incident(iid)
        self.assertEqual(inc["estado"], "RESUELTA")
        self.assertEqual(int(inc["resolved_by"]), 222222222)
        self.assertIsNotNone(inc["resolved_at"])

    def test_validar_cierra_con_closed_by(self):
        iid = self._seed("RESUELTA")
        r = storage.update_incident_state_atomic(
            iid, "CERRADA", self.ENC, ["RESUELTA"], action="validar")
        self.assertTrue(r["success"])
        inc = storage.get_incident(iid)
        self.assertEqual(inc["estado"], "CERRADA")
        self.assertEqual(int(inc["closed_by"]), 444444444)
        self.assertIsNotNone(inc["closed_at"])
        self.assertIsNotNone(inc["resolution_time_minutes"])

    def test_reabrir_vuelve_a_asignada_sin_borrar_assignee(self):
        iid = self._seed("NUEVA")
        storage.update_incident_state_atomic(
            iid, "ASIGNADA", self.ENC, ["NUEVA"],
            action="asignar", assignee_telegram_id=222222222)
        storage.update_incident_state_atomic(iid, "EN_PROCESO", self.EMP, ["ASIGNADA"], action="comenzar")
        storage.update_incident_state_atomic(iid, "RESUELTA", self.EMP, ["EN_PROCESO"], action="terminado")
        r = storage.update_incident_state_atomic(
            iid, "ASIGNADA", self.ENC, ["RESUELTA"], action="reabrir")
        self.assertTrue(r["success"])
        inc = storage.get_incident(iid)
        self.assertEqual(inc["estado"], "ASIGNADA")
        self.assertEqual(int(inc["assigned_to_telegram_id"]), 222222222)

    def test_cancelar_guarda_motivo(self):
        iid = self._seed("ASIGNADA")
        r = storage.update_incident_state_atomic(
            iid, "CANCELADA", self.ENC, ["NUEVA", "ASIGNADA", "EN_PROCESO", "RESUELTA"],
            action="cancelar", cancel_reason="duplicada")
        self.assertTrue(r["success"])
        inc = storage.get_incident(iid)
        self.assertEqual(inc["estado"], "CANCELADA")
        self.assertEqual(int(inc["cancelled_by"]), 444444444)
        self.assertEqual(inc["cancel_reason"], "duplicada")

    def test_transicion_invalida_rechazada(self):
        iid = self._seed("NUEVA")
        r = storage.update_incident_state_atomic(
            iid, "RESUELTA", self.EMP, ["EN_PROCESO"], action="terminado")
        self.assertFalse(r["success"])
        self.assertIn("NUEVA", r["reason"])

    def test_doble_click_idempotente(self):
        iid = self._seed("NUEVA")
        storage.update_incident_state_atomic(iid, "ASIGNADA", self.ENC, ["NUEVA"], action="tomar")
        r = storage.update_incident_state_atomic(iid, "ASIGNADA", self.ENC, ["NUEVA"], action="tomar")
        self.assertFalse(r["success"])

    def test_get_incident_inexistente(self):
        self.assertIsNone(storage.get_incident(99999))


class TestKeyboard(unittest.TestCase):

    def _callbacks(self, kb):
        return [b.callback_data for row in kb.inline_keyboard for b in row]

    def test_keyboard_nueva(self):
        kb = build_keyboard_for_state(42, "NUEVA")
        cbs = self._callbacks(kb)
        self.assertIn("incident_action:42:asignar", cbs)
        self.assertIn("incident_action:42:tomar", cbs)
        self.assertIn("incident_action:42:cancelar", cbs)

    def test_keyboard_asignada(self):
        kb = build_keyboard_for_state(42, "ASIGNADA")
        cbs = self._callbacks(kb)
        self.assertIn("incident_action:42:comenzar", cbs)
        self.assertIn("incident_action:42:reasignar", cbs)

    def test_keyboard_en_proceso(self):
        kb = build_keyboard_for_state(42, "EN_PROCESO")
        self.assertIn("incident_action:42:terminado", self._callbacks(kb))

    def test_keyboard_resuelta(self):
        cbs = self._callbacks(build_keyboard_for_state(42, "RESUELTA"))
        self.assertIn("incident_action:42:validar", cbs)
        self.assertIn("incident_action:42:reabrir", cbs)

    def test_keyboard_cerrada_none(self):
        self.assertIsNone(build_keyboard_for_state(42, "CERRADA"))

    def test_keyboard_cancelada_none(self):
        self.assertIsNone(build_keyboard_for_state(42, "CANCELADA"))

    def test_callback_dentro_limite(self):
        kb = build_keyboard_for_state(9999, "NUEVA")
        for cb in self._callbacks(kb):
            self.assertLessEqual(len(cb.encode()), 64)


class TestAssignKeyboards(unittest.TestCase):
    def test_assign_keyboard_lista_personas_y_para_mi(self):
        from notifier import build_assign_keyboard
        kb = build_assign_keyboard(7, [(222222222, "Andrei"), (444444444, "Carlos")])
        cbs = [b.callback_data for row in kb.inline_keyboard for b in row]
        self.assertIn("assign_to:7:222222222", cbs)
        self.assertIn("assign_to:7:444444444", cbs)
        self.assertIn("incident_action:7:tomar", cbs)  # botón "Para mí"

    def test_dept_menu_keyboard(self):
        from notifier import build_dept_menu_keyboard
        kb = build_dept_menu_keyboard(7, ["MANTENIMIENTO", "HOUSEKEEPING"])
        cbs = [b.callback_data for row in kb.inline_keyboard for b in row]
        self.assertIn("assign_dept:7:MANTENIMIENTO", cbs)
        self.assertIn("assign_dept:7:HOUSEKEEPING", cbs)


class TestPermissions(unittest.TestCase):

    EMPLOYEES = {
        444444444: {"nombre": "Carlos Encargado Mant", "departamento": "MANTENIMIENTO", "rol": "ENCARGADO"},
        555555555: {"nombre": "Laura Encargada HK", "departamento": "HOUSEKEEPING", "rol": "ENCARGADO"},
        777777777: {"nombre": "Alfredo Gerente", "departamento": "GENERAL", "rol": "GERENTE_GENERAL"},
        111111111: {"nombre": "María García", "departamento": "HOUSEKEEPING", "rol": "EMPLEADO"},
    }

    INCIDENT_MANT = {"categoria": "MANTENIMIENTO", "tipo": "INCIDENCIA"}
    INCIDENT_HK = {"categoria": "LIMPIEZA", "tipo": "INCIDENCIA"}

    # 10. Encargado de mantenimiento puede actuar sobre incidencia de MANTENIMIENTO
    def test_encargado_mant_puede_actuar_mant(self):
        carlos = self.EMPLOYEES[444444444]
        self.assertTrue(permissions.can_act_on_incident(carlos, self.INCIDENT_MANT))

    # 11. Encargado de HK NO puede actuar sobre incidencia de MANTENIMIENTO
    def test_encargado_hk_no_puede_actuar_mant(self):
        laura = self.EMPLOYEES[555555555]
        self.assertFalse(permissions.can_act_on_incident(laura, self.INCIDENT_MANT))

    # 12. Gerente general puede actuar sobre cualquier incidencia
    def test_gerente_puede_actuar_cualquier_incidencia(self):
        alfredo = self.EMPLOYEES[777777777]
        self.assertTrue(permissions.can_act_on_incident(alfredo, self.INCIDENT_MANT))
        self.assertTrue(permissions.can_act_on_incident(alfredo, self.INCIDENT_HK))

    # Empleado no puede actuar
    def test_empleado_no_puede_actuar(self):
        maria = self.EMPLOYEES[111111111]
        self.assertFalse(permissions.can_act_on_incident(maria, self.INCIDENT_MANT))


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Security test — actor identity must come from query.from_user.id
# ---------------------------------------------------------------------------

import pytest
from unittest.mock import AsyncMock, MagicMock

EMPLEADOS_SEC = {
    111111111: {"nombre": "María García", "departamento": "HOUSEKEEPING",
                "rol": "EMPLEADO", "telegram_id": 111111111},
    444444444: {"nombre": "Carlos Encargado", "departamento": "MANTENIMIENTO",
                "rol": "ENCARGADO", "telegram_id": 444444444},
}


@pytest.mark.asyncio
async def test_callback_actor_is_from_user_id(tmp_path):
    """Actor identity comes from query.from_user.id — EMPLEADO is rejected."""
    db_path = tmp_path / "test.db"
    with patch.object(storage, "DB_PATH", db_path):
        storage.init_db()
        with storage._conn() as con:
            from datetime import datetime
            cur = con.execute(
                """INSERT INTO classifications
                   (timestamp, employee_name, employee_dept, message, tipo, prioridad,
                    categoria, ubicacion, descripcion, estado)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (datetime.now().isoformat(timespec="seconds"),
                 "Ana", "HK", "test", "INCIDENCIA", "ALTA",
                 "MANTENIMIENTO", "Hab 1", "test", "ABIERTA"),
            )
            iid = cur.lastrowid

        query = MagicMock()
        query.from_user.id = 111111111
        query.data = f"incident_action:{iid}:tomar"
        query.answer = AsyncMock()

        context = MagicMock()
        context.bot_data = {"employees": EMPLEADOS_SEC}

        from handlers.callback_handler import _handle_incident_action
        await _handle_incident_action(query, context)

        query.answer.assert_called_once()
        answer_text = query.answer.call_args[0][0]
        assert "permisos" in answer_text.lower()

        inc = storage.get_incident(iid)
        assert inc["estado"] == "ABIERTA"
