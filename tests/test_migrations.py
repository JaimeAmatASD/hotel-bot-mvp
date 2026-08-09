import sys, tempfile
from pathlib import Path
from unittest.mock import patch
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
