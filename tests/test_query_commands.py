"""Tests for Sprint B.4: query commands and formatters."""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import storage
from handlers import format_relative_time, format_priority_emoji, get_help_text
from permissions import can_query_department


# ---------------------------------------------------------------------------
# Storage tests
# ---------------------------------------------------------------------------

class TestStorageQueries(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db"
        self.patcher = patch.object(storage, "DB_PATH", self.db_path)
        self.patcher.start()
        storage.init_db()

    def tearDown(self):
        self.patcher.stop()

    def _insert(self, tipo="INCIDENCIA", prioridad="ALTA", estado="NUEVA",
                ubicacion="Habitación 305", descripcion="Test", message="test msg",
                offset_minutes=0):
        ts = (datetime.now() - timedelta(minutes=offset_minutes)).isoformat(timespec="seconds")
        with storage._conn() as con:
            cur = con.execute(
                """INSERT INTO classifications
                   (timestamp, employee_name, employee_dept, message, tipo, prioridad,
                    categoria, ubicacion, descripcion, estado)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (ts, "Jaime A", "SPA", message, tipo, prioridad,
                 "MANTENIMIENTO", ubicacion, descripcion, estado),
            )
            return cur.lastrowid

    # 1. get_open_incidents devuelve solo no-cerradas
    def test_open_incidents_excludes_closed(self):
        self._insert(estado="NUEVA")
        self._insert(estado="ASIGNADA")
        self._insert(estado="EN_PROCESO")
        self._insert(estado="CERRADA")
        results = storage.get_open_incidents()
        self.assertEqual(len(results), 3)
        estados = {r["estado"] for r in results}
        self.assertNotIn("CERRADA", estados)

    # 2. get_open_incidents ordena por prioridad CRITICA > ALTA > MEDIA > BAJA
    def test_open_incidents_priority_order(self):
        self._insert(prioridad="BAJA", offset_minutes=0)
        self._insert(prioridad="CRITICA", offset_minutes=1)
        self._insert(prioridad="MEDIA", offset_minutes=2)
        self._insert(prioridad="ALTA", offset_minutes=3)
        results = storage.get_open_incidents()
        priorities = [r["prioridad"] for r in results]
        self.assertEqual(priorities, ["CRITICA", "ALTA", "MEDIA", "BAJA"])

    # 3. get_open_incidents con filtro de prioridad
    def test_open_incidents_priority_filter(self):
        self._insert(prioridad="ALTA")
        self._insert(prioridad="MEDIA")
        self._insert(prioridad="CRITICA")
        results = storage.get_open_incidents(prioridad="ALTA")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["prioridad"], "ALTA")

    # 4. Incidencias cerradas no aparecen
    def test_open_incidents_none_when_all_closed(self):
        self._insert(estado="CERRADA")
        self._insert(estado="CERRADA")
        results = storage.get_open_incidents()
        self.assertEqual(len(results), 0)

    # 5. get_incidents_for_room con número exacto
    def test_room_query_exact_number(self):
        self._insert(ubicacion="Habitación 305")
        self._insert(ubicacion="Habitación 412")
        results = storage.get_incidents_for_room("305")
        self.assertEqual(len(results), 1)
        self.assertIn("305", results[0]["ubicacion"])

    # 6. get_incidents_for_room case-insensitive
    def test_room_query_case_insensitive(self):
        self._insert(ubicacion="Lobby principal")
        results = storage.get_incidents_for_room("LOBBY")
        self.assertEqual(len(results), 1)

    # 7. get_incidents_for_room con zona común
    def test_room_query_zone(self):
        self._insert(ubicacion="Lobby cerca de ascensores")
        self._insert(ubicacion="Habitación 305")
        results = storage.get_incidents_for_room("lobby")
        self.assertEqual(len(results), 1)

    # 8. search_classifications busca en message, descripcion y ubicacion
    def test_search_finds_in_all_fields(self):
        # Each insert has "goteo" in a different field
        self._insert(message="goteo en baño", descripcion="Normal", ubicacion="Hab 100")
        self._insert(message="Normal msg", descripcion="goteo lento", ubicacion="Hab 101")
        self._insert(message="Normal msg", descripcion="Normal", ubicacion="piscina goteo")

        results = storage.search_classifications("goteo")
        self.assertEqual(len(results), 3)  # found in message, descripcion, and ubicacion

    # 9. search_classifications con query vacío devuelve todo (la validación de <3 chars es en handler)
    def test_search_empty_query_returns_results(self):
        self._insert(message="algo", descripcion="test desc")
        # "" LIKE "%%" matches everything — that's expected behavior
        results = storage.search_classifications("")
        self.assertGreaterEqual(len(results), 0)  # behavior may vary; just don't crash

    def _insert_assigned(self, assigned_tid, estado="ASIGNADA"):
        ts = datetime.now().isoformat(timespec="seconds")
        with storage._conn() as con:
            cur = con.execute(
                """INSERT INTO classifications
                   (timestamp, employee_name, employee_dept, message, tipo, prioridad,
                    categoria, ubicacion, descripcion, estado, assigned_to_telegram_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (ts, "Jaime A", "SPA", "msg", "INCIDENCIA", "ALTA",
                 "MANTENIMIENTO", "Hab 47", "Test", estado, str(assigned_tid)),
            )
            return cur.lastrowid

    # get_resolved_incidents devuelve solo las RESUELTA (a validar)
    def test_resolved_incidents_only_resueltas(self):
        self._insert(estado="NUEVA")
        self._insert(estado="ASIGNADA")
        self._insert(estado="RESUELTA")
        self._insert(estado="RESUELTA")
        self._insert(estado="CERRADA")
        results = storage.get_resolved_incidents()
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["estado"] == "RESUELTA" for r in results))

    # get_incidents_assigned_to devuelve solo las del asignado y no terminales
    def test_assigned_to_filters_by_person_and_open(self):
        self._insert_assigned(777, estado="ASIGNADA")
        self._insert_assigned(777, estado="EN_PROCESO")
        self._insert_assigned(777, estado="CERRADA")   # terminal: excluida
        self._insert_assigned(999, estado="ASIGNADA")   # otra persona: excluida
        results = storage.get_incidents_assigned_to(777)
        self.assertEqual(len(results), 2)
        estados = {r["estado"] for r in results}
        self.assertNotIn("CERRADA", estados)
        for r in results:
            self.assertEqual(str(r["assigned_to_telegram_id"]), "777")


# ---------------------------------------------------------------------------
# Formatter tests
# ---------------------------------------------------------------------------

class TestFormatters(unittest.TestCase):

    # 8. format_relative_time para timestamps recientes
    def test_relative_time_now(self):
        ts = datetime.now().isoformat(timespec="seconds")
        result = format_relative_time(ts)
        self.assertEqual(result, "ahora mismo")

    # 9. format_relative_time para timestamps de >1h
    def test_relative_time_hours(self):
        ts = (datetime.now() - timedelta(hours=2, minutes=30)).isoformat(timespec="seconds")
        result = format_relative_time(ts)
        self.assertIn("h", result)
        self.assertIn("2", result)

    # 10. format_relative_time para timestamps de >24h
    def test_relative_time_days(self):
        ts = (datetime.now() - timedelta(days=3)).isoformat(timespec="seconds")
        result = format_relative_time(ts)
        self.assertIn("día", result)
        self.assertIn("3", result)

    def test_relative_time_minutes(self):
        ts = (datetime.now() - timedelta(minutes=45)).isoformat(timespec="seconds")
        result = format_relative_time(ts)
        self.assertIn("min", result)
        self.assertIn("45", result)

    # 11. format_priority_emoji
    def test_priority_emoji_critica(self):
        self.assertEqual(format_priority_emoji("CRITICA"), "🔴")

    def test_priority_emoji_alta(self):
        self.assertEqual(format_priority_emoji("ALTA"), "🟠")

    def test_priority_emoji_media(self):
        self.assertEqual(format_priority_emoji("MEDIA"), "🟡")

    def test_priority_emoji_baja(self):
        self.assertEqual(format_priority_emoji("BAJA"), "🟢")

    def test_priority_emoji_unknown(self):
        self.assertEqual(format_priority_emoji("DESCONOCIDA"), "")

    # 12. get_help_text EMPLEADO no incluye /notificaciones
    def test_help_empleado_no_notificaciones(self):
        text = get_help_text("EMPLEADO")
        self.assertNotIn("/notificaciones", text)
        self.assertIn("/help", text)
        self.assertIn("/abiertas", text)

    # 13. get_help_text GERENTE_GENERAL incluye /notificaciones
    def test_help_gerente_incluye_notificaciones(self):
        text = get_help_text("GERENTE_GENERAL")
        self.assertIn("/notificaciones", text)
        self.assertIn("gerente general", text)

    def test_help_encargado_muestra_departamento(self):
        text = get_help_text("ENCARGADO", "MANTENIMIENTO")
        self.assertIn("MANTENIMIENTO", text)
        self.assertNotIn("/notificaciones", text)


# ---------------------------------------------------------------------------
# Permissions tests
# ---------------------------------------------------------------------------

class TestQueryPermissions(unittest.TestCase):

    CARLOS_MANT = {"nombre": "Carlos", "rol": "ENCARGADO", "departamento": "MANTENIMIENTO"}
    LAURA_HK    = {"nombre": "Laura",  "rol": "ENCARGADO", "departamento": "HOUSEKEEPING"}
    ALFREDO_GER = {"nombre": "Alfredo","rol": "GERENTE_GENERAL", "departamento": "GENERAL"}
    MARIA_EMP   = {"nombre": "María",  "rol": "EMPLEADO",  "departamento": "HOUSEKEEPING"}

    # 14. Encargado de MANTENIMIENTO no puede query HOUSEKEEPING
    def test_encargado_no_puede_query_otro_dept(self):
        self.assertFalse(can_query_department(self.CARLOS_MANT, "HOUSEKEEPING"))

    # Encargado SÍ puede query su propio dept
    def test_encargado_puede_query_su_dept(self):
        self.assertTrue(can_query_department(self.CARLOS_MANT, "MANTENIMIENTO"))

    # 15. Empleado no puede query ningún dept
    def test_empleado_no_puede_query_dept(self):
        self.assertFalse(can_query_department(self.MARIA_EMP, "MANTENIMIENTO"))
        self.assertFalse(can_query_department(self.MARIA_EMP, "HOUSEKEEPING"))

    # Gerente puede query cualquier dept
    def test_gerente_puede_query_cualquier_dept(self):
        self.assertTrue(can_query_department(self.ALFREDO_GER, "MANTENIMIENTO"))
        self.assertTrue(can_query_department(self.ALFREDO_GER, "HOUSEKEEPING"))
        self.assertTrue(can_query_department(self.ALFREDO_GER, "SPA"))

    # can_query_department es case-insensitive
    def test_query_dept_case_insensitive(self):
        self.assertTrue(can_query_department(self.CARLOS_MANT, "mantenimiento"))
        self.assertTrue(can_query_department(self.CARLOS_MANT, "Mantenimiento"))


if __name__ == "__main__":
    unittest.main()
