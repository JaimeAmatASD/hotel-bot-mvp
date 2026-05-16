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


def _seed_incident(con, tipo="INCIDENCIA", categoria="Sanitarios", estado="ABIERTA"):
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

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db"
        self.patcher = patch.object(storage, "DB_PATH", self.db_path)
        self.patcher.start()
        storage.init_db()

    def tearDown(self):
        self.patcher.stop()

    def _seed(self, estado="ABIERTA", categoria="Sanitarios"):
        with storage._conn() as con:
            return _seed_incident(con, categoria=categoria, estado=estado)

    # 1. Tomar incidencia ABIERTA → ASIGNADA
    def test_tomar_abierta_cambia_a_asignada(self):
        iid = self._seed("ABIERTA")
        result = storage.update_incident_state(iid, "ASIGNADA", 444444444)
        self.assertTrue(result["success"])
        self.assertEqual(result["new_state"], "ASIGNADA")
        inc = storage.get_incident(iid)
        self.assertEqual(inc["estado"], "ASIGNADA")
        self.assertEqual(int(inc["assigned_to_telegram_id"]), 444444444)
        self.assertIsNotNone(inc["assigned_at"])

    # 2. Tomar incidencia ya ASIGNADA → falla
    def test_tomar_asignada_falla(self):
        iid = self._seed("ASIGNADA")
        result = storage.update_incident_state(iid, "ASIGNADA", 444444444)
        self.assertFalse(result["success"])
        self.assertIn("ASIGNADA", result["reason"])

    # 3. EN_PROCESO desde ABIERTA → cambia y asigna actor
    def test_proceso_desde_abierta_asigna_actor(self):
        iid = self._seed("ABIERTA")
        result = storage.update_incident_state(iid, "EN_PROCESO", 444444444)
        self.assertTrue(result["success"])
        inc = storage.get_incident(iid)
        self.assertEqual(inc["estado"], "EN_PROCESO")
        self.assertEqual(int(inc["assigned_to_telegram_id"]), 444444444)

    # 4. EN_PROCESO desde ASIGNADA → cambia sin tocar assignee original
    def test_proceso_desde_asignada_no_toca_assignee(self):
        iid = self._seed("ABIERTA")
        storage.update_incident_state(iid, "ASIGNADA", 444444444)
        storage.update_incident_state(iid, "EN_PROCESO", 777777777)
        inc = storage.get_incident(iid)
        self.assertEqual(inc["estado"], "EN_PROCESO")
        # Original assignee preserved
        self.assertEqual(int(inc["assigned_to_telegram_id"]), 444444444)

    # 5. Cerrar desde ASIGNADA → CERRADA con closed_at y resolution_time
    def test_cerrar_desde_asignada_guarda_tiempos(self):
        iid = self._seed("ABIERTA")
        storage.update_incident_state(iid, "ASIGNADA", 444444444)
        result = storage.update_incident_state(iid, "CERRADA", 444444444)
        self.assertTrue(result["success"])
        inc = storage.get_incident(iid)
        self.assertEqual(inc["estado"], "CERRADA")
        self.assertIsNotNone(inc["closed_at"])
        self.assertIsNotNone(inc["resolution_time_minutes"])

    # 6. Cerrar ya CERRADA → falla
    def test_cerrar_cerrada_falla(self):
        iid = self._seed("CERRADA")
        result = storage.update_incident_state(iid, "CERRADA", 444444444)
        self.assertFalse(result["success"])
        self.assertIn("CERRADA", result["reason"])

    # 7. Cerrar desde ABIERTA también funciona
    def test_cerrar_desde_abierta(self):
        iid = self._seed("ABIERTA")
        result = storage.update_incident_state(iid, "CERRADA", 444444444)
        self.assertTrue(result["success"])
        self.assertEqual(result["new_state"], "CERRADA")

    # 8. get_incident devuelve None para id inexistente
    def test_get_incident_inexistente(self):
        result = storage.get_incident(99999)
        self.assertIsNone(result)


class TestKeyboard(unittest.TestCase):

    # 7 (del criterio). build_keyboard ABIERTA → 3 botones
    def test_keyboard_abierta_tres_botones(self):
        kb = build_keyboard_for_state(42, "ABIERTA", 444444444)
        self.assertIsNotNone(kb)
        buttons = kb.inline_keyboard[0]
        self.assertEqual(len(buttons), 3)
        callbacks = [b.callback_data for b in buttons]
        self.assertIn("incident_action:42:tomar:444444444", callbacks)
        self.assertIn("incident_action:42:proceso:444444444", callbacks)
        self.assertIn("incident_action:42:cerrar:444444444", callbacks)

    # 8. build_keyboard ASIGNADA → 2 botones
    def test_keyboard_asignada_dos_botones(self):
        kb = build_keyboard_for_state(42, "ASIGNADA", 444444444)
        self.assertIsNotNone(kb)
        self.assertEqual(len(kb.inline_keyboard[0]), 2)

    # 8 (criterio). build_keyboard EN_PROCESO → 1 botón
    def test_keyboard_en_proceso_un_boton(self):
        kb = build_keyboard_for_state(42, "EN_PROCESO", 444444444)
        self.assertIsNotNone(kb)
        self.assertEqual(len(kb.inline_keyboard[0]), 1)
        self.assertEqual(kb.inline_keyboard[0][0].callback_data, "incident_action:42:cerrar:444444444")

    # 9. build_keyboard CERRADA → None
    def test_keyboard_cerrada_none(self):
        kb = build_keyboard_for_state(42, "CERRADA", 444444444)
        self.assertIsNone(kb)

    # Callback data dentro del límite de 64 bytes
    def test_callback_data_dentro_limite_telegram(self):
        kb = build_keyboard_for_state(9999, "ABIERTA", 9999999999)
        for btn in kb.inline_keyboard[0]:
            self.assertLessEqual(len(btn.callback_data.encode()), 64)


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
