"""Tests for Sprint B.5: event log, atomic transitions, timeline formatters."""
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import storage
import permissions
from handlers import build_timeline_text, calculate_total_time, format_incident_history


class TestEventLog(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db"
        self.patcher = patch.object(storage, "DB_PATH", self.db_path)
        self.patcher.start()
        storage.init_db()

    def tearDown(self):
        self.patcher.stop()

    def _seed_incident(self, estado="NUEVA"):
        with storage._conn() as con:
            cur = con.execute(
                """INSERT INTO classifications
                   (timestamp, employee_name, employee_dept, message, tipo, prioridad,
                    categoria, ubicacion, descripcion, estado)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    datetime.now().isoformat(timespec="seconds"),
                    "Jaime A", "SPA", "test", "INCIDENCIA", "ALTA",
                    "MANTENIMIENTO", "Habitación 305", "Baño roto", estado,
                ),
            )
            return cur.lastrowid

    ACTOR_CARLOS = {
        "telegram_id": 444444444,
        "nombre": "Carlos Encargado Mant",
        "rol": "ENCARGADO",
        "departamento": "MANTENIMIENTO",
    }

    # 1. save_event con campos mínimos
    def test_save_event_minimal(self):
        iid = self._seed_incident()
        eid = storage.save_event(incident_id=iid, actor_telegram_id=444, action="created")
        self.assertIsNotNone(eid)
        self.assertGreater(eid, 0)

    # 2. save_event con extra JSON — round-trip
    def test_save_event_extra_json_roundtrip(self):
        iid = self._seed_incident()
        storage.save_event(
            incident_id=iid,
            actor_telegram_id=0,
            action="notification_sent",
            extra={"recipient": 444, "redirect_mode": "admin"},
        )
        events = storage.get_events_for_incident(iid)
        self.assertEqual(len(events), 1)
        extra = events[0]["extra"]
        self.assertIsInstance(extra, dict)
        self.assertEqual(extra["recipient"], 444)
        self.assertEqual(extra["redirect_mode"], "admin")

    # 3. get_events_for_incident ordenado por timestamp ASC
    def test_events_ordered_asc(self):
        iid = self._seed_incident()
        storage.save_event(incident_id=iid, actor_telegram_id=1, action="created")
        storage.save_event(incident_id=iid, actor_telegram_id=2, action="tomar")
        storage.save_event(incident_id=iid, actor_telegram_id=3, action="cerrar")
        events = storage.get_events_for_incident(iid)
        actions = [e["action"] for e in events]
        self.assertEqual(actions, ["created", "tomar", "cerrar"])

    # 4. update_incident_state_atomic NUEVA→ASIGNADA: success + evento "tomar"
    def test_atomic_tomar_abierta(self):
        iid = self._seed_incident("NUEVA")
        result = storage.update_incident_state_atomic(iid, "ASIGNADA", self.ACTOR_CARLOS, ["NUEVA"], action="tomar")
        self.assertTrue(result["success"])
        self.assertEqual(result["from_state"], "NUEVA")
        self.assertEqual(result["to_state"], "ASIGNADA")
        events = storage.get_events_for_incident(iid)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["action"], "tomar")
        self.assertEqual(events[0]["success"], 1)

    # 5. update_incident_state_atomic con estado no en expected: rechaza + evento rejected
    def test_atomic_rejected_wrong_state(self):
        iid = self._seed_incident("ASIGNADA")
        result = storage.update_incident_state_atomic(iid, "ASIGNADA", self.ACTOR_CARLOS, ["NUEVA"], action="tomar")
        self.assertFalse(result["success"])
        events = storage.get_events_for_incident(iid)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["action"], "action_rejected_already_done")
        self.assertEqual(events[0]["success"], 0)

    # 5b. terminado directo desde ASIGNADA (comenzar es opcional)
    def test_atomic_terminado_directo_desde_asignada(self):
        from config.transitions import EXPECTED_FROM
        iid = self._seed_incident("ASIGNADA")
        result = storage.update_incident_state_atomic(
            iid, "RESUELTA", self.ACTOR_CARLOS, EXPECTED_FROM["terminado"], action="terminado")
        self.assertTrue(result["success"])
        self.assertEqual(result["from_state"], "ASIGNADA")
        self.assertEqual(result["to_state"], "RESUELTA")
        events = storage.get_events_for_incident(iid)
        self.assertEqual(events[-1]["action"], "terminado")
        self.assertEqual(events[-1]["success"], 1)

    # 6. CERRADA→cualquier: rechaza
    def test_atomic_rejected_cerrada(self):
        iid = self._seed_incident("CERRADA")
        result = storage.update_incident_state_atomic(iid, "CERRADA", self.ACTOR_CARLOS, ["NUEVA", "ASIGNADA", "EN_PROCESO"], action="validar")
        self.assertFalse(result["success"])

    # 7. Test de concurrencia con threading
    def test_concurrent_tomar_only_one_wins(self):
        iid = self._seed_incident("NUEVA")
        results = []
        barrier = threading.Barrier(2)

        def try_tomar(actor_id):
            barrier.wait()  # ambos arrancan al mismo tiempo
            actor = {**self.ACTOR_CARLOS, "telegram_id": actor_id}
            r = storage.update_incident_state_atomic(iid, "ASIGNADA", actor, ["NUEVA"], action="tomar")
            results.append(r)

        t1 = threading.Thread(target=try_tomar, args=(444,))
        t2 = threading.Thread(target=try_tomar, args=(555,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(len(results), 2)
        successes = [r for r in results if r["success"]]
        failures = [r for r in results if not r["success"]]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)

        events = storage.get_events_for_incident(iid)
        success_events = [e for e in events if e["action"] == "tomar" and e["success"] == 1]
        reject_events = [e for e in events if e["action"] == "action_rejected_already_done"]
        self.assertEqual(len(success_events), 1)
        self.assertEqual(len(reject_events), 1)

    # 17. Evento verificable tras atomic
    def test_atomic_event_in_db(self):
        iid = self._seed_incident("ASIGNADA")
        storage.update_incident_state_atomic(iid, "EN_PROCESO", self.ACTOR_CARLOS, ["ASIGNADA"], action="comenzar")
        events = storage.get_events_for_incident(iid)
        self.assertEqual(events[0]["action"], "comenzar")
        self.assertEqual(events[0]["actor_name"], "Carlos Encargado Mant")


class TestFormatters(unittest.TestCase):

    def _make_events(self, actions):
        """Helper: construye lista de eventos sintéticos."""
        base = datetime(2026, 5, 17, 14, 30, 0)
        events = []
        for i, (action, actor, success) in enumerate(actions):
            ts = (base + timedelta(minutes=i * 10)).isoformat(timespec="seconds")
            events.append({
                "action": action,
                "actor_name": actor,
                "actor_role": "ENCARGADO",
                "timestamp": ts,
                "success": 1 if success else 0,
                "from_state": None,
                "to_state": None,
                "reason": None,
                "extra": None,
            })
        return events

    # 8. build_timeline_text con created+asignar+validar
    def test_build_timeline_three_lines(self):
        events = self._make_events([
            ("created", "Jaime A", True),
            ("asignar", "Carlos E", True),
            ("validar", "Carlos E", True),
        ])
        text = build_timeline_text(events)
        self.assertIn("Reportada", text)
        self.assertIn("Asignada", text)
        self.assertIn("Validada", text)

    # 9. build_timeline_text filtra notification_sent
    def test_build_timeline_filters_notifications(self):
        events = self._make_events([
            ("created", "Jaime A", True),
            ("notification_sent", "sistema", True),
            ("tomar", "Carlos E", True),
        ])
        text = build_timeline_text(events)
        self.assertNotIn("Notificación", text)
        self.assertIn("Tomada", text)

    # 10. calculate_total_time con 83 min
    def test_total_time_hours_and_minutes(self):
        base = datetime(2026, 5, 17, 14, 0, 0)
        events = [
            {"action": "created", "timestamp": base.isoformat(timespec="seconds"), "success": 1},
            {"action": "validar", "timestamp": (base + timedelta(minutes=83)).isoformat(timespec="seconds"), "success": 1},
        ]
        result = calculate_total_time(events)
        self.assertEqual(result, "1h 23min")

    # 11. calculate_total_time con <1 min
    def test_total_time_less_than_minute(self):
        base = datetime.now()
        events = [
            {"action": "created", "timestamp": base.isoformat(timespec="seconds"), "success": 1},
            {"action": "validar", "timestamp": (base + timedelta(seconds=30)).isoformat(timespec="seconds"), "success": 1},
        ]
        result = calculate_total_time(events)
        self.assertEqual(result, "menos de 1 min")

    # 12. calculate_total_time sin evento cerrar
    def test_total_time_no_close_event(self):
        events = [
            {"action": "created", "timestamp": datetime.now().isoformat(timespec="seconds"), "success": 1},
        ]
        result = calculate_total_time(events)
        self.assertEqual(result, "")

    # 13. format_incident_history contiene display_id
    def test_incident_history_contains_display_id(self):
        incident = {
            "id": 42,
            "prioridad": "ALTA",
            "ubicacion": "Habitación 305",
            "descripcion": "Baño roto",
            "employee_name": "Jaime A",
        }
        events = self._make_events([("created", "Jaime A", True)])
        text = format_incident_history(incident, events)
        self.assertIn("INC-042", text)

    # 14. format_incident_history muestra ❌ para evento rejected
    def test_incident_history_shows_rejected(self):
        incident = {
            "id": 42,
            "prioridad": "ALTA",
            "ubicacion": "Habitación 305",
            "descripcion": "Baño roto",
        }
        events = self._make_events([
            ("created", "Jaime A", True),
            ("action_rejected_no_permission", "Laura HK", False),
        ])
        text = format_incident_history(incident, events)
        self.assertIn("❌", text)


class TestHistorialPermissions(unittest.TestCase):

    INCIDENT_MANT = {
        "id": 1,
        "tipo": "INCIDENCIA",
        "categoria": "MANTENIMIENTO",
        "employee_name": "Jaime A",
        "descripcion": "test",
        "ubicacion": "hab 305",
        "prioridad": "ALTA",
    }

    EMPLOYEES = {
        7391337590: {"nombre": "Jaime A", "departamento": "SPA", "rol": "EMPLEADO"},
        444444444:  {"nombre": "Carlos", "departamento": "MANTENIMIENTO", "rol": "ENCARGADO"},
        555555555:  {"nombre": "Laura",  "departamento": "HOUSEKEEPING", "rol": "ENCARGADO"},
        777777777:  {"nombre": "Alfredo","departamento": "GENERAL", "rol": "GERENTE_GENERAL"},
    }

    # 15. Empleado ve historial de su propio reporte
    def test_empleado_ve_su_propio_reporte(self):
        jaime = self.EMPLOYEES[7391337590]
        self.assertTrue(permissions.can_see_incident(jaime, self.INCIDENT_MANT))

    # 16. Encargado HK no ve historial de MANTENIMIENTO
    def test_encargado_hk_no_ve_mantenimiento(self):
        laura = self.EMPLOYEES[555555555]
        self.assertFalse(permissions.can_see_incident(laura, self.INCIDENT_MANT))

    def test_gerente_ve_todo(self):
        alfredo = self.EMPLOYEES[777777777]
        self.assertTrue(permissions.can_see_incident(alfredo, self.INCIDENT_MANT))

    def test_encargado_mant_ve_mantenimiento(self):
        carlos = self.EMPLOYEES[444444444]
        self.assertTrue(permissions.can_see_incident(carlos, self.INCIDENT_MANT))


if __name__ == "__main__":
    unittest.main()
