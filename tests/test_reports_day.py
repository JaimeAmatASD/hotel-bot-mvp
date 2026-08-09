"""Consultas del informe por día calendario y arrastre de pendientes."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import storage


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    with patch.object(storage, "DB_PATH", tmp_path / "reports_day.db"):
        storage.init_db()
        yield


def _insert(con, **kw):
    campos = {"timestamp": "2026-08-09T10:00:00", "employee_name": "Jaime A",
              "employee_telegram_id": 111, "message": "x", "tipo": "INCIDENCIA",
              "descripcion": "algo", "estado": "NUEVA", "report_id": None}
    campos.update(kw)
    cols = ",".join(campos)
    ph = ",".join("?" * len(campos))
    con.execute(f"INSERT INTO classifications ({cols}) VALUES ({ph})", list(campos.values()))


def test_day_query_ignores_report_id():
    """Un ítem ya consolidado sigue apareciendo: ese filtro era el que comía ítems."""
    with storage._conn() as con:
        _insert(con, descripcion="ya en un informe", report_id=7)
        _insert(con, descripcion="suelto")
    items = storage.get_classifications_for_employee_day(111, "2026-08-09")
    assert {i["descripcion"] for i in items} == {"ya en un informe", "suelto"}


def test_day_query_is_scoped_to_the_day_and_person():
    with storage._conn() as con:
        _insert(con, descripcion="hoy")
        _insert(con, descripcion="ayer", timestamp="2026-08-08T23:59:59")
        _insert(con, descripcion="otro empleado", employee_telegram_id=222)
    items = storage.get_classifications_for_employee_day(111, "2026-08-09")
    assert [i["descripcion"] for i in items] == ["hoy"]


def test_day_query_excludes_no_reporte_and_error():
    with storage._conn() as con:
        _insert(con, descripcion="válido")
        _insert(con, descripcion="ruido", tipo="NO_REPORTE")
        _insert(con, descripcion="fallo", tipo="ERROR")
    items = storage.get_classifications_for_employee_day(111, "2026-08-09")
    assert [i["descripcion"] for i in items] == ["válido"]


def test_carryover_only_open_incidents_from_earlier_days():
    with storage._conn() as con:
        _insert(con, descripcion="vieja abierta", timestamp="2026-07-02T10:00:00", estado="NUEVA")
        _insert(con, descripcion="vieja asignada", timestamp="2026-07-06T10:00:00", estado="ASIGNADA")
        _insert(con, descripcion="vieja cerrada", timestamp="2026-07-06T11:00:00", estado="CERRADA")
        _insert(con, descripcion="vieja cancelada", timestamp="2026-07-06T12:00:00", estado="CANCELADA")
        _insert(con, descripcion="vieja observación", timestamp="2026-07-06T13:00:00",
                tipo="OBSERVACION", estado=None)
        _insert(con, descripcion="de hoy abierta", timestamp="2026-08-09T09:00:00", estado="NUEVA")
    arrastre = storage.get_open_incidents_before_day(111, "2026-08-09")
    assert [i["descripcion"] for i in arrastre] == ["vieja abierta", "vieja asignada"]


def test_carryover_includes_items_already_in_a_report():
    """El criterio es 'sigue sin resolverse', no 'nunca se consolidó'."""
    with storage._conn() as con:
        _insert(con, descripcion="abierta y ya informada",
                timestamp="2026-07-02T10:00:00", estado="NUEVA", report_id=3)
    arrastre = storage.get_open_incidents_before_day(111, "2026-08-09")
    assert [i["descripcion"] for i in arrastre] == ["abierta y ya informada"]


def test_carryover_is_ordered_oldest_first():
    """La plantilla muestra solo las primeras N: tienen que ser las más viejas."""
    with storage._conn() as con:
        _insert(con, descripcion="media", timestamp="2026-07-06T10:00:00")
        _insert(con, descripcion="la más vieja", timestamp="2026-06-29T10:00:00")
        _insert(con, descripcion="reciente", timestamp="2026-08-08T10:00:00")
    arrastre = storage.get_open_incidents_before_day(111, "2026-08-09")
    assert [i["descripcion"] for i in arrastre] == ["la más vieja", "media", "reciente"]
