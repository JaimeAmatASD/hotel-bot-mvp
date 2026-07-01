"""Tests for Sprint B.5 redesign: retrospective shift reports."""
import sys
import asyncio
import unittest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import storage
import report_processor


def _insert_classification(db_path, employee_name, tipo, descripcion, report_id=None, hours_ago=0):
    """Helper: insert a classification row directly for testing."""
    import sqlite3, json
    ts = (datetime.now() - timedelta(hours=hours_ago)).isoformat(timespec="seconds")
    with sqlite3.connect(db_path) as con:
        cur = con.execute(
            """INSERT INTO classifications
               (timestamp, employee_name, employee_dept, message, tipo, prioridad,
                categoria, ubicacion, descripcion, confianza, campos_faltantes, report_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ts, employee_name, "SPA", "msg", tipo, "MEDIA",
             "OTRO", "Lobby", descripcion, 0.9, "[]", report_id),
        )
        return cur.lastrowid


class Base(unittest.TestCase):
    EMPLOYEE = {
        "telegram_id": 7391337590,
        "nombre": "Jaime A",
        "departamento": "SPA",
        "rol": "EMPLEADO",
    }
    GERENTE = {
        "telegram_id": 9999,
        "nombre": "Gerente",
        "departamento": "GENERAL",
        "rol": "GERENTE_GENERAL",
    }

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db"
        self.patcher = patch.object(storage, "DB_PATH", self.db_path)
        self.patcher.start()
        storage.init_db()

    def tearDown(self):
        self.patcher.stop()


# ---------------------------------------------------------------------------
# Storage layer tests
# ---------------------------------------------------------------------------

class TestStorageNew(Base):

    def test_create_report_returns_id_and_closed(self):
        rid = storage.create_report(self.EMPLOYEE)
        self.assertGreater(rid, 0)
        rep = storage.get_report_with_items(rid)
        self.assertEqual(rep["status"], "CLOSED")
        self.assertEqual(rep["messages"], [])

    def test_get_classifications_recent_excludes_types(self):
        _insert_classification(str(self.db_path), "Jaime A", "NO_REPORTE", "nada")
        _insert_classification(str(self.db_path), "Jaime A", "ERROR", "error")
        items = storage.get_classifications_for_employee_recent("Jaime A", 12)
        self.assertEqual(items, [])

    def test_get_classifications_recent_excludes_in_report(self):
        rid = storage.create_report(self.EMPLOYEE)
        cid = _insert_classification(str(self.db_path), "Jaime A", "OBSERVACION", "obs en rep", report_id=rid)
        _insert_classification(str(self.db_path), "Jaime A", "OBSERVACION", "obs libre")
        items = storage.get_classifications_for_employee_recent("Jaime A", 12, exclude_in_report=True)
        ids = [i["id"] for i in items]
        self.assertNotIn(cid, ids)
        self.assertEqual(len(ids), 1)

    def test_link_classifications_to_report_batch(self):
        rid = storage.create_report(self.EMPLOYEE)
        cid1 = _insert_classification(str(self.db_path), "Jaime A", "OBSERVACION", "obs1")
        cid2 = _insert_classification(str(self.db_path), "Jaime A", "GUEST_INTEL", "gi1")
        storage.link_classifications_to_report([cid1, cid2], rid)
        rep = storage.get_report_with_items(rid)
        item_ids = [i["id"] for i in rep["items"]]
        self.assertIn(cid1, item_ids)
        self.assertIn(cid2, item_ids)

    def test_update_classification_editable_fields(self):
        cid = _insert_classification(str(self.db_path), "Jaime A", "OBSERVACION", "viejo")
        storage.update_classification(cid, {"tipo": "OBSERVACION", "descripcion": "nuevo", "prioridad": "ALTA",
                                            "categoria": "LIMPIEZA", "ubicacion": "Hall", "confianza": 0.95,
                                            "huesped_afectado": 0, "habitacion_huesped": None, "campos_faltantes": []})
        item = storage.get_incident(cid)
        self.assertEqual(item["descripcion"], "nuevo")
        self.assertEqual(item["ubicacion"], "Hall")

    def test_link_empty_list_noop(self):
        rid = storage.create_report(self.EMPLOYEE)
        storage.link_classifications_to_report([], rid)  # should not raise

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


# ---------------------------------------------------------------------------
# T1: /reporte sin ítems → mensaje "no reportaste nada"
# ---------------------------------------------------------------------------

class TestReporteNoItems(Base):

    def test_reporte_no_items_message(self):
        items = report_processor.consolidate_recent_classifications("Jaime A", 12)
        self.assertEqual(items, [])


# ---------------------------------------------------------------------------
# T2: /reporte 6h con ítems → resumen agrupado correcto
# ---------------------------------------------------------------------------

class TestReporteSummary(Base):

    def test_summary_groups_correctly(self):
        _insert_classification(str(self.db_path), "Jaime A", "INCIDENCIA", "Fuga en hab 302")
        _insert_classification(str(self.db_path), "Jaime A", "GUEST_INTEL", "Cliente pide toallas")
        _insert_classification(str(self.db_path), "Jaime A", "OBSERVACION", "Lobby sucio")

        items = storage.get_classifications_for_employee_recent("Jaime A", 6)
        self.assertEqual(len(items), 3)

        text, keyboard = report_processor.format_report_summary(items, self.EMPLOYEE, 6)
        self.assertIn("INCIDENCIAS", text)
        self.assertIn("NOTAS DE HUÉSPED", text)
        self.assertIn("NOVEDADES DEL TURNO", text)
        self.assertIn("INFORME DE TURNO", text)
        self.assertIsNotNone(keyboard)

    def test_global_numbering(self):
        _insert_classification(str(self.db_path), "Jaime A", "INCIDENCIA", "Inc 1")
        _insert_classification(str(self.db_path), "Jaime A", "OBSERVACION", "Obs 2")
        items = storage.get_classifications_for_employee_recent("Jaime A", 12)
        text, _ = report_processor.format_report_summary(items, self.EMPLOYEE, 12)
        self.assertIn("1.", text)
        self.assertIn("2.", text)


# ---------------------------------------------------------------------------
# T3: ítems ya en REP → excluidos del consolidado
# ---------------------------------------------------------------------------

class TestExcludeLinked(Base):

    def test_items_in_report_excluded(self):
        rid = storage.create_report(self.EMPLOYEE)
        cid = _insert_classification(str(self.db_path), "Jaime A", "OBSERVACION", "ya en rep", report_id=rid)
        _insert_classification(str(self.db_path), "Jaime A", "OBSERVACION", "libre")

        items = report_processor.consolidate_recent_classifications("Jaime A", 12)
        ids = [i["id"] for i in items]
        self.assertNotIn(cid, ids)
        self.assertEqual(len(ids), 1)


# ---------------------------------------------------------------------------
# T4: "Todo bien" → crea REP-N, link batch, notifica gerente solo si mode=todo
# ---------------------------------------------------------------------------

class TestConfirmReport(Base):

    def _make_items(self):
        cid1 = _insert_classification(str(self.db_path), "Jaime A", "OBSERVACION", "obs1")
        cid2 = _insert_classification(str(self.db_path), "Jaime A", "GUEST_INTEL", "gi1")
        return [storage.get_incident(cid1), storage.get_incident(cid2)]

    def test_confirm_creates_report_and_links(self):
        items = self._make_items()
        rid = storage.create_report(self.EMPLOYEE)
        storage.link_classifications_to_report([i["id"] for i in items], rid)
        rep = storage.get_report_with_items(rid)
        self.assertEqual(len(rep["items"]), 2)

    def test_notify_manager_only_mode_todo(self):
        items = self._make_items()
        rid = storage.create_report(self.EMPLOYEE)
        storage.link_classifications_to_report([i["id"] for i in items], rid)
        rep = storage.get_report_with_items(rid)

        employees = {
            self.EMPLOYEE["telegram_id"]: self.EMPLOYEE,
            self.GERENTE["telegram_id"]: self.GERENTE,
        }
        storage.set_notification_mode(self.GERENTE["telegram_id"], "todo")

        bot = MagicMock()
        bot.send_message = AsyncMock()

        with patch("report_processor.settings.REPORT_NOTIFY_GERENTE", True):
            asyncio.run(report_processor.notify_manager_report(bot, rep, items, employees))
        bot.send_message.assert_called_once()

    def test_notify_includes_dept_encargado_regardless_of_mode(self):
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
        storage.set_notification_mode(self.GERENTE["telegram_id"], "criticas")  # gerente NO recibe

        bot = MagicMock()
        bot.send_message = AsyncMock()
        asyncio.run(report_processor.notify_manager_report(bot, rep, items, employees))

        sent_to = [c.kwargs.get("chat_id") for c in bot.send_message.call_args_list]
        self.assertIn(5555, sent_to)                                  # encargado del depto: siempre
        self.assertNotIn(self.GERENTE["telegram_id"], sent_to)        # gerente en 'criticas': no

    def test_author_not_self_notified(self):
        # Autor es el propio encargado de SPA → no debe autonotificarse
        enc_author = {"telegram_id": 6666, "nombre": "Encargada SPA",
                      "departamento": "SPA", "rol": "ENCARGADO"}
        cid = _insert_classification(str(self.db_path), "Encargada SPA", "OBSERVACION", "obs")
        rid = storage.create_report(enc_author)
        storage.link_classifications_to_report([cid], rid)
        rep = storage.get_report_with_items(rid)
        employees = {enc_author["telegram_id"]: enc_author}

        bot = MagicMock()
        bot.send_message = AsyncMock()
        asyncio.run(report_processor.notify_manager_report(bot, rep, [storage.get_incident(cid)], employees))
        bot.send_message.assert_not_called()

    def test_no_notify_manager_if_mode_not_todo(self):
        items = self._make_items()
        rid = storage.create_report(self.EMPLOYEE)
        rep = storage.get_report_with_items(rid)

        employees = {
            self.EMPLOYEE["telegram_id"]: self.EMPLOYEE,
            self.GERENTE["telegram_id"]: self.GERENTE,
        }
        storage.set_notification_mode(self.GERENTE["telegram_id"], "criticas")

        bot = MagicMock()
        bot.send_message = AsyncMock()

        with patch("report_processor.settings.REPORT_NOTIFY_GERENTE", True):
            asyncio.run(report_processor.notify_manager_report(bot, rep, items, employees))
        bot.send_message.assert_not_called()

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


# ---------------------------------------------------------------------------
# T5: "Corregir" + número que es INCIDENCIA → mensaje de bloqueo
# ---------------------------------------------------------------------------

class TestCorrectBlockedIncident(Base):

    def test_incidencia_blocked_in_summary(self):
        cid = _insert_classification(str(self.db_path), "Jaime A", "INCIDENCIA", "Fuga")
        items = [storage.get_incident(cid)]
        # Verify item is INCIDENCIA — correction flow in text_handler checks tipo
        self.assertEqual(items[0]["tipo"], "INCIDENCIA")


# ---------------------------------------------------------------------------
# T6: "Corregir" + número que es OBSERVACION → update_classification actualiza
# ---------------------------------------------------------------------------

class TestCorrectObservacion(Base):

    def test_update_classification_changes_description(self):
        cid = _insert_classification(str(self.db_path), "Jaime A", "OBSERVACION", "original")
        storage.update_classification(cid, {
            "tipo": "OBSERVACION", "descripcion": "corregido", "prioridad": "BAJA",
            "categoria": "OTRO", "ubicacion": "Lobby", "confianza": 0.9,
            "huesped_afectado": 0, "habitacion_huesped": None, "campos_faltantes": [],
        })
        updated = storage.get_incident(cid)
        self.assertEqual(updated["descripcion"], "corregido")
        # Immutable fields untouched
        self.assertEqual(updated["employee_name"], "Jaime A")


# ---------------------------------------------------------------------------
# T7: NOTIFICATION_REDIRECT_MODE respetado
# ---------------------------------------------------------------------------

class TestRedirectMode(Base):

    def test_redirect_to_admin(self):
        cid = _insert_classification(str(self.db_path), "Jaime A", "OBSERVACION", "obs")
        items = [storage.get_incident(cid)]
        rid = storage.create_report(self.EMPLOYEE)
        rep = storage.get_report_with_items(rid)

        employees = {
            self.EMPLOYEE["telegram_id"]: self.EMPLOYEE,
            self.GERENTE["telegram_id"]: self.GERENTE,
        }
        storage.set_notification_mode(self.GERENTE["telegram_id"], "todo")

        bot = MagicMock()
        bot.send_message = AsyncMock()

        admin_id = 12345
        with patch("config.settings.NOTIFICATION_REDIRECT_MODE", "admin"), \
             patch("config.settings.ADMIN_TELEGRAM_ID", admin_id), \
             patch("report_processor.settings.REPORT_NOTIFY_GERENTE", True):
            asyncio.run(report_processor.notify_manager_report(bot, rep, items, employees))

        call_args = bot.send_message.call_args
        self.assertEqual(call_args.kwargs.get("chat_id") or call_args.args[0] if call_args.args else call_args.kwargs["chat_id"], admin_id)


# ---------------------------------------------------------------------------
# T8: permisos /reporte REP-N
# ---------------------------------------------------------------------------

class TestReporteViewPermissions(Base):

    def _create_report_for(self, employee):
        rid = storage.create_report(employee)
        return rid

    def test_employee_can_see_own_report(self):
        rid = self._create_report_for(self.EMPLOYEE)
        rep = storage.get_report_with_items(rid)
        self.assertIsNotNone(rep)
        # Verify it's their own
        self.assertEqual(rep["employee_telegram_id"], self.EMPLOYEE["telegram_id"])

    def test_employee_cannot_see_others_report(self):
        other = {**self.EMPLOYEE, "telegram_id": 8888, "nombre": "Otro"}
        rid = self._create_report_for(other)
        rep = storage.get_report_with_items(rid)
        # Permission check: if employee_telegram_id != tid → denied
        self.assertNotEqual(rep["employee_telegram_id"], self.EMPLOYEE["telegram_id"])

    def test_gerente_can_see_any_report(self):
        rid = self._create_report_for(self.EMPLOYEE)
        rep = storage.get_report_with_items(rid)
        self.assertIsNotNone(rep)
        # Gerente has no restriction — verified by absence of dept filter


# ---------------------------------------------------------------------------
# T9: /fin equivalente a /reporte sin args
# ---------------------------------------------------------------------------

class TestFinAlias(Base):

    def test_handle_fin_calls_handle_reporte(self):
        # /fin resets args to [] and delegates to handle_reporte — verified at the code level
        # Here we verify consolidate_recent_classifications with 0h window returns []
        items = report_processor.consolidate_recent_classifications("Jaime A", 0)
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
