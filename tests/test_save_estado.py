"""Regresión: save() debe escribir estado=NUEVA explícitamente, sin depender
del DEFAULT de la columna. DBs legadas tienen `estado TEXT DEFAULT 'ABIERTA'`,
lo que dejaba incidencias nuevas en ABIERTA y rompía la asignación."""
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import storage
from storage import classifications
from config.enums import IncidentState


def _crear_tabla_legada(db_path: Path) -> None:
    """Crea classifications con el DEFAULT legado 'ABIERTA'."""
    con = sqlite3.connect(str(db_path))
    con.execute(
        """CREATE TABLE classifications (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp        TEXT NOT NULL,
            employee_name    TEXT NOT NULL,
            employee_dept    TEXT,
            message          TEXT NOT NULL,
            tipo             TEXT,
            prioridad        TEXT,
            categoria        TEXT,
            ubicacion        TEXT,
            confianza        REAL,
            campos_faltantes TEXT,
            habitacion       TEXT,
            huesped_afectado INTEGER,
            descripcion      TEXT,
            photo_path       TEXT,
            estado           TEXT DEFAULT 'ABIERTA'
        )"""
    )
    con.commit()
    con.close()


def test_save_fuerza_nueva_sobre_default_legado_abierta():
    with tempfile.TemporaryDirectory() as d:
        db_path = Path(d) / "legacy.db"
        with patch.object(storage, "DB_PATH", db_path):
            _crear_tabla_legada(db_path)
            # Como en producción: init_db() corre al arranque y aplica los ALTER
            # (columnas nuevas) sin tocar el DEFAULT legado de `estado`.
            storage.init_db()
            inc_id = classifications.save(
                {"nombre": "Jaime A", "departamento": "MANTENIMIENTO"},
                "Mancha de humedad en habitación 47",
                {"tipo": "INCIDENCIA", "prioridad": "ALTA"},
            )
            inc = classifications.get_incident(inc_id)

    assert inc["estado"] == IncidentState.NUEVA, (
        f"esperaba NUEVA, obtuve {inc['estado']!r} (default legado se filtró)"
    )


def test_save_persiste_subcategoria_en_db_legada():
    with tempfile.TemporaryDirectory() as d:
        db_path = Path(d) / "legacy.db"
        with patch.object(storage, "DB_PATH", db_path):
            _crear_tabla_legada(db_path)
            storage.init_db()
            inc_id = classifications.save(
                {"nombre": "Jaime A", "departamento": "MANTENIMIENTO"},
                "Pierde agua el grifo de la 204",
                {
                    "tipo": "INCIDENCIA",
                    "prioridad": "ALTA",
                    "categoria": "MANTENIMIENTO",
                    "subcategoria": "FONTANERIA",
                },
            )
            inc = classifications.get_incident(inc_id)

    assert inc["subcategoria"] == "FONTANERIA"
