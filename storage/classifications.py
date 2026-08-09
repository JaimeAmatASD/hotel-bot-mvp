"""Classifications CRUD: save, get_incident, update, room queries, search."""
import json
from datetime import datetime, timedelta

from config.enums import IncidentState
from storage._conn import _conn


def save(employee: dict, message: str, result: dict) -> int:
    with _conn() as con:
        cur = con.execute("""
            INSERT INTO classifications
            (timestamp, employee_name, employee_dept, employee_telegram_id, message, tipo, prioridad,
             categoria, subcategoria, ubicacion, confianza, campos_faltantes, habitacion,
             huesped_afectado, descripcion, photo_path, estado)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            datetime.now().isoformat(timespec="seconds"),
            employee["nombre"],
            employee.get("departamento"),
            employee.get("telegram_id"),
            message,
            result.get("tipo"),
            result.get("prioridad"),
            result.get("categoria"),
            result.get("subcategoria"),
            result.get("ubicacion"),
            result.get("confianza"),
            json.dumps(result.get("campos_faltantes", []), ensure_ascii=False),
            result.get("habitacion_huesped"),
            int(result.get("huesped_afectado") or 0),
            result.get("descripcion"),
            result.get("_meta", {}).get("photo_path"),
            IncidentState.NUEVA,
        ))
        return cur.lastrowid


def get_incident(incident_id: int) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM classifications WHERE id = ?", (incident_id,)
        ).fetchone()
    return dict(row) if row else None


def get_incident_assignee(incident_id: int) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT assigned_to_telegram_id FROM classifications WHERE id = ?",
            (incident_id,),
        ).fetchone()
    if not row or not row["assigned_to_telegram_id"]:
        return None
    return {"telegram_id": row["assigned_to_telegram_id"]}


def update_classification(classification_id: int, result: dict) -> None:
    """Updates editable fields. Immutable fields are never touched."""
    with _conn() as con:
        con.execute(
            """UPDATE classifications SET
               tipo = ?, prioridad = ?, categoria = ?, subcategoria = ?, ubicacion = ?,
               descripcion = ?, huesped_afectado = ?, habitacion = ?,
               campos_faltantes = ?, confianza = ?
               WHERE id = ?""",
            (
                result.get("tipo"),
                result.get("prioridad"),
                result.get("categoria"),
                result.get("subcategoria"),
                result.get("ubicacion"),
                result.get("descripcion"),
                int(result.get("huesped_afectado") or 0),
                result.get("habitacion_huesped"),
                json.dumps(result.get("campos_faltantes", []), ensure_ascii=False),
                result.get("confianza"),
                classification_id,
            ),
        )


def get_incidents_for_room(room_or_zone: str, days_back: int = 30) -> list[dict]:
    since = (datetime.now() - timedelta(days=days_back)).replace(hour=0, minute=0, second=0, microsecond=0)
    with _conn() as con:
        rows = con.execute(
            """SELECT * FROM classifications
               WHERE tipo = 'INCIDENCIA'
                 AND LOWER(ubicacion) LIKE LOWER(?)
                 AND timestamp >= ?
               ORDER BY timestamp DESC""",
            (f"%{room_or_zone}%", since.isoformat()),
        ).fetchall()
    return [dict(r) for r in rows]


def get_guest_intel_for_room(room: str, days_back: int = 30) -> list[dict]:
    since = (datetime.now() - timedelta(days=days_back)).isoformat(timespec="seconds")
    with _conn() as con:
        rows = con.execute(
            """SELECT * FROM classifications
               WHERE tipo = 'GUEST_INTEL'
                 AND LOWER(ubicacion) LIKE LOWER(?)
                 AND timestamp >= ?
               ORDER BY timestamp DESC""",
            (f"%{room}%", since),
        ).fetchall()
    return [dict(r) for r in rows]


def get_observations_for_room(room_or_zone: str, days_back: int = 30) -> list[dict]:
    since = (datetime.now() - timedelta(days=days_back)).isoformat(timespec="seconds")
    with _conn() as con:
        rows = con.execute(
            """SELECT * FROM classifications
               WHERE tipo = 'OBSERVACION'
                 AND LOWER(ubicacion) LIKE LOWER(?)
                 AND timestamp >= ?
               ORDER BY timestamp DESC""",
            (f"%{room_or_zone}%", since),
        ).fetchall()
    return [dict(r) for r in rows]


def search_classifications(query: str, days_back: int = 90, limit: int = 10) -> list[dict]:
    since = (datetime.now() - timedelta(days=days_back)).isoformat(timespec="seconds")
    pattern = f"%{query}%"
    with _conn() as con:
        rows = con.execute(
            """SELECT * FROM classifications
               WHERE timestamp >= ?
                 AND (LOWER(message) LIKE LOWER(?)
                   OR LOWER(descripcion) LIKE LOWER(?)
                   OR LOWER(ubicacion) LIKE LOWER(?)
                   OR LOWER(subcategoria) LIKE LOWER(?))
               ORDER BY timestamp DESC
               LIMIT ?""",
            (since, pattern, pattern, pattern, pattern, limit),
        ).fetchall()
    return [dict(r) for r in rows]
