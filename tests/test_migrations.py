import sqlite3
import sys, tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import storage
from storage.migrations import apply_pending


def _cols(con, table):
    return [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]


def test_columnas_trazabilidad_existen():
    with tempfile.TemporaryDirectory() as d:
        with patch.object(storage, "DB_PATH", Path(d) / "t.db"):
            storage.init_db()
            with storage._conn() as con:
                cols = _cols(con, "classifications")
    for c in ("assigned_by", "resolved_by", "resolved_at", "closed_by",
              "cancelled_by", "cancel_reason"):
        assert c in cols, f"falta columna {c}"


def test_columna_subcategoria_existe():
    with tempfile.TemporaryDirectory() as d:
        with patch.object(storage, "DB_PATH", Path(d) / "t.db"):
            storage.init_db()
            with storage._conn() as con:
                cols = _cols(con, "classifications")
    assert "subcategoria" in cols


def test_default_estado_es_nueva():
    with tempfile.TemporaryDirectory() as d:
        with patch.object(storage, "DB_PATH", Path(d) / "t.db"):
            storage.init_db()
            with storage._conn() as con:
                con.execute(
                    "INSERT INTO classifications (timestamp, employee_name, message) "
                    "VALUES ('2026-01-01','Ana','x')"
                )
                estado = con.execute(
                    "SELECT estado FROM classifications LIMIT 1"
                ).fetchone()[0]
    assert estado == "NUEVA"


def test_migracion_renombra_abierta_a_nueva():
    with tempfile.TemporaryDirectory() as d:
        with patch.object(storage, "DB_PATH", Path(d) / "t.db"):
            storage.init_db()
            with storage._conn() as con:
                con.execute(
                    "INSERT INTO classifications (timestamp, employee_name, message, estado) "
                    "VALUES ('2026-01-01','Ana','x','ABIERTA')"
                )
            apply_pending()
            with storage._conn() as con:
                estados = [r[0] for r in con.execute(
                    "SELECT estado FROM classifications").fetchall()]
    assert estados == ["NUEVA"]
    assert "ABIERTA" not in estados


def test_v2_backfills_telegram_id_from_name():
    """Las filas viejas sin telegram_id lo heredan de otra fila con el mismo nombre."""
    with tempfile.TemporaryDirectory() as d:
        with patch.object(storage, "DB_PATH", Path(d) / "t.db"):
            storage.init_db()
            with storage._conn() as con:
                con.execute(
                    "INSERT INTO classifications (timestamp, employee_name, employee_telegram_id,"
                    " message, tipo, descripcion) VALUES"
                    " ('2026-07-01T10:00:00','Jaime A',7391337590,'x','INCIDENCIA','con id')")
                con.execute(
                    "INSERT INTO classifications (timestamp, employee_name, employee_telegram_id,"
                    " message, tipo, descripcion) VALUES"
                    " ('2026-06-01T10:00:00','Jaime A',NULL,'x','INCIDENCIA','sin id')")
            apply_pending()
            with storage._conn() as con:
                rows = con.execute(
                    "SELECT descripcion, employee_telegram_id FROM classifications"
                    " ORDER BY descripcion").fetchall()
    assert dict(rows) == {"con id": 7391337590, "sin id": 7391337590}


def test_v3_merges_same_day_duplicate_reports():
    """Dos informes del mismo empleado el mismo día se fusionan en el de id menor."""
    with tempfile.TemporaryDirectory() as d:
        with patch.object(storage, "DB_PATH", Path(d) / "t.db"):
            storage.init_db()
            with storage._conn() as con:
                for closed in ("2026-07-01T16:57:01", "2026-07-01T17:37:19"):
                    con.execute(
                        "INSERT INTO reports (employee_telegram_id, employee_name, started_at,"
                        " closed_at, status) VALUES (8709342265,'Juan',?,?,'CLOSED')",
                        (closed, closed))
                con.execute(
                    "INSERT INTO classifications (timestamp, employee_name, message, tipo,"
                    " descripcion, report_id)"
                    " VALUES ('2026-07-01T16:00:00','Juan','x','INCIDENCIA','del primero',1)")
                con.execute(
                    "INSERT INTO classifications (timestamp, employee_name, message, tipo,"
                    " descripcion, report_id)"
                    " VALUES ('2026-07-01T17:00:00','Juan','x','INCIDENCIA','del segundo',2)")
            apply_pending()
            with storage._conn() as con:
                ids = [r[0] for r in con.execute("SELECT id FROM reports ORDER BY id")]
                linked = [r[0] for r in con.execute(
                    "SELECT report_id FROM classifications ORDER BY timestamp")]
                fecha = con.execute("SELECT report_date FROM reports WHERE id=1").fetchone()[0]
                cerrado = con.execute("SELECT closed_at FROM reports WHERE id=1").fetchone()[0]
    assert ids == [1], "el duplicado debe desaparecer"
    assert linked == [1, 1], "los ítems de ambos quedan en el informe sobreviviente"
    assert fecha == "2026-07-01"
    assert cerrado == "2026-07-01T17:37:19", "gana el cierre más tardío"


def test_v3_unique_index_blocks_second_report_same_day():
    """Después de migrar, la base misma impide dos informes del mismo día."""
    with tempfile.TemporaryDirectory() as d:
        with patch.object(storage, "DB_PATH", Path(d) / "t.db"):
            storage.init_db()
            apply_pending()
            with storage._conn() as con:
                con.execute(
                    "INSERT INTO reports (employee_telegram_id, employee_name, started_at,"
                    " closed_at, status, report_date)"
                    " VALUES (1,'A','x','x','CLOSED','2026-08-09')")
            with pytest.raises(sqlite3.IntegrityError):
                with storage._conn() as con:
                    con.execute(
                        "INSERT INTO reports (employee_telegram_id, employee_name, started_at,"
                        " closed_at, status, report_date)"
                        " VALUES (1,'A','y','y','CLOSED','2026-08-09')")
