"""Tests for Sprint B.5-reports: accumulative shift reports."""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import storage
from report_processor import (
    is_open_keyword, is_close_keyword, _normalize,
    format_report_summary, format_report_for_manager,
)


class TestReportStorage(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db"
        self.patcher = patch.object(storage, "DB_PATH", self.db_path)
        self.patcher.start()
        storage.init_db()

    def tearDown(self):
        self.patcher.stop()

    EMPLOYEE = {
        "telegram_id": 7391337590,
        "nombre": "Jaime A",
        "departamento": "SPA",
        "rol": "GERENTE_GENERAL",
    }

    # 1. open_report crea OPEN y devuelve id
    def test_open_report_creates_open(self):
        rid = storage.open_report(self.EMPLOYEE)
        self.assertGreater(rid, 0)
        rep = storage.get_report_with_items(rid)
        self.assertEqual(rep["status"], "OPEN")
        self.assertEqual(rep["employee_name"], "Jaime A")

    # 2. open_report idempotente
    def test_open_report_idempotent(self):
        rid1 = storage.open_report(self.EMPLOYEE)
        rid2 = storage.open_report(self.EMPLOYEE)
        self.assertEqual(rid1, rid2)

    # 3. add_message_to_report añade y devuelve id
    def test_add_message_returns_id(self):
        rid = storage.open_report(self.EMPLOYEE)
        mid = storage.add_message_to_report(rid, "text", "se rompió algo")
        self.assertGreater(mid, 0)

    # 4. get_report_messages ordenados ASC
    def test_messages_ordered_asc(self):
        rid = storage.open_report(self.EMPLOYEE)
        storage.add_message_to_report(rid, "text", "primero")
        storage.add_message_to_report(rid, "text", "segundo")
        storage.add_message_to_report(rid, "text", "tercero")
        msgs = storage.get_report_messages(rid)
        contents = [m["content"] for m in msgs]
        self.assertEqual(contents, ["primero", "segundo", "tercero"])

    # 5. close_report marca CLOSED + closure_type
    def test_close_report(self):
        rid = storage.open_report(self.EMPLOYEE)
        storage.close_report(rid, "manual")
        rep = storage.get_report_with_items(rid)
        self.assertEqual(rep["status"], "CLOSED")
        self.assertEqual(rep["closure_type"], "manual")
        self.assertIsNotNone(rep["closed_at"])

    # 6. get_expired_open_reports con timeout 0h devuelve abiertos
    def test_get_expired_with_zero_hours(self):
        rid = storage.open_report(self.EMPLOYEE)
        # Force started_at to be old enough
        with storage._conn() as con:
            con.execute(
                "UPDATE reports SET started_at = ? WHERE id = ?",
                ((datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds"), rid),
            )
        expired = storage.get_expired_open_reports(timeout_hours=0)
        ids = [r["id"] for r in expired]
        self.assertIn(rid, ids)

    # Non-expired reports are NOT returned
    def test_not_expired_not_returned(self):
        rid = storage.open_report(self.EMPLOYEE)
        expired = storage.get_expired_open_reports(timeout_hours=24)
        ids = [r["id"] for r in expired]
        self.assertNotIn(rid, ids)

    # 14. link_classification_to_report
    def test_link_classification_to_report(self):
        rid = storage.open_report(self.EMPLOYEE)
        with storage._conn() as con:
            cur = con.execute(
                """INSERT INTO classifications
                   (timestamp, employee_name, employee_dept, message, tipo, prioridad,
                    categoria, ubicacion, descripcion)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (datetime.now().isoformat(), "Jaime A", "SPA", "test",
                 "OBSERVACION", "BAJA", "OTRO", "Lobby", "Test obs"),
            )
            cid = cur.lastrowid
        storage.link_classification_to_report(cid, rid)
        rep = storage.get_report_with_items(rid)
        item_ids = [i["id"] for i in rep["items"]]
        self.assertIn(cid, item_ids)

    # 15. get_report_with_items devuelve reporte + mensajes + items
    def test_get_report_with_items_structure(self):
        rid = storage.open_report(self.EMPLOYEE)
        storage.add_message_to_report(rid, "text", "mensaje 1")
        rep = storage.get_report_with_items(rid)
        self.assertIn("messages", rep)
        self.assertIn("items", rep)
        self.assertEqual(len(rep["messages"]), 1)

    # get_open_report_for_employee returns None after close
    def test_no_open_report_after_close(self):
        rid = storage.open_report(self.EMPLOYEE)
        storage.close_report(rid)
        open_rep = storage.get_open_report_for_employee(self.EMPLOYEE["telegram_id"])
        self.assertIsNone(open_rep)


class TestKeywords(unittest.TestCase):

    # 7. is_open_keyword matches expected phrases
    def test_open_keyword_exact(self):
        self.assertTrue(is_open_keyword("inicio reporte"))

    def test_open_keyword_uppercase(self):
        self.assertTrue(is_open_keyword("INICIO REPORTE"))

    def test_open_keyword_with_de(self):
        self.assertTrue(is_open_keyword("inicio de reporte"))

    def test_open_keyword_abrir(self):
        self.assertTrue(is_open_keyword("abrir reporte"))

    # 11. Accent tolerance
    def test_open_keyword_accented(self):
        # "répórte" normalizes to "reporte"
        self.assertTrue(is_open_keyword("inicio répórte"))

    # 8. is_close_keyword matches expected phrases
    def test_close_keyword_cierre(self):
        self.assertTrue(is_close_keyword("cierre de reporte"))

    def test_close_keyword_cerrar(self):
        self.assertTrue(is_close_keyword("cerrar reporte"))

    def test_close_keyword_fin(self):
        self.assertTrue(is_close_keyword("fin reporte"))

    # 9. Normal messages don't match open
    def test_normal_message_not_open(self):
        self.assertFalse(is_open_keyword("se rompió la luz en la habitación 302"))
        self.assertFalse(is_open_keyword("el baño tiene una fuga"))

    # 10. Normal messages don't match close
    def test_normal_message_not_close(self):
        self.assertFalse(is_close_keyword("el cliente de la 207 pide más toallas"))
        self.assertFalse(is_close_keyword("observación del lobby"))


class TestFormatters(unittest.TestCase):

    def _make_item(self, tipo, descripcion="Test description", ubicacion="Hab 305"):
        return {
            "content": "test content",
            "photo_path": None,
            "message_type": "text",
            "result": {
                "tipo": tipo,
                "descripcion": descripcion,
                "ubicacion": ubicacion,
                "prioridad": "ALTA",
                "categoria": "MANTENIMIENTO",
            },
        }

    def _make_report(self, report_id=1):
        return {
            "id": report_id,
            "employee_name": "Jaime A",
            "employee_department": "SPA",
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "status": "OPEN",
        }

    EMPLOYEE = {"nombre": "Jaime A", "departamento": "SPA"}

    # 12. format_report_summary contiene sección de incidencias
    def test_summary_has_incidencias_section(self):
        decomposed = {
            "incidencias": [self._make_item("INCIDENCIA")],
            "guest_intel": [],
            "observaciones": [],
            "no_reportes": [],
            "errors": [],
            "all_items": [self._make_item("INCIDENCIA")],
        }
        text, keyboard = format_report_summary(self._make_report(), decomposed, self.EMPLOYEE)
        self.assertIn("incidencia", text.lower())
        self.assertIsNotNone(keyboard)

    # 13. format_report_summary muestra count correcto
    def test_summary_count(self):
        items = [self._make_item("INCIDENCIA"), self._make_item("INCIDENCIA")]
        decomposed = {
            "incidencias": items,
            "guest_intel": [self._make_item("GUEST_INTEL")],
            "observaciones": [],
            "no_reportes": [],
            "errors": [],
            "all_items": items + [self._make_item("GUEST_INTEL")],
        }
        text, _ = format_report_summary(self._make_report(), decomposed, self.EMPLOYEE)
        self.assertIn("3", text)  # total 3 items

    def test_manager_summary_format(self):
        items = [self._make_item("INCIDENCIA"), self._make_item("GUEST_INTEL")]
        decomposed = {
            "incidencias": [items[0]],
            "guest_intel": [items[1]],
            "observaciones": [],
            "no_reportes": [],
            "errors": [],
            "all_items": items,
        }
        text = format_report_for_manager(self._make_report(), decomposed, "REP-001")
        self.assertIn("REP-001", text)
        self.assertIn("incidencia", text.lower())


if __name__ == "__main__":
    unittest.main()
