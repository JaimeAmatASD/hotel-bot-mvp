"""Read-only queries for UI commands: /abiertas, /history, dashboards."""
import json
from datetime import datetime
from storage._conn import _conn


_PRIORITY_ORDER = (
    "CASE prioridad WHEN 'CRITICA' THEN 1 WHEN 'ALTA' THEN 2 "
    "WHEN 'MEDIA' THEN 3 WHEN 'BAJA' THEN 4 ELSE 5 END"
)


def get_open_incidents(prioridad: str | None = None, limit: int = 100) -> list[dict]:
    params: list = []
    where = "tipo = 'INCIDENCIA' AND (estado IS NULL OR estado IN ('NUEVA', 'ASIGNADA', 'EN_PROCESO', 'RESUELTA'))"
    if prioridad:
        where += " AND prioridad = ?"
        params.append(prioridad.upper())
    params.append(limit)
    with _conn() as con:
        rows = con.execute(
            f"SELECT * FROM classifications WHERE {where} ORDER BY {_PRIORITY_ORDER} ASC, timestamp ASC LIMIT ?",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def get_incidents_assigned_to(telegram_id: int, limit: int = 100) -> list[dict]:
    """Incidencias no terminales asignadas a una persona (para /mistareas)."""
    with _conn() as con:
        rows = con.execute(
            f"""SELECT * FROM classifications
                WHERE tipo = 'INCIDENCIA'
                  AND assigned_to_telegram_id = ?
                  AND estado IN ('ASIGNADA', 'EN_PROCESO', 'RESUELTA')
                ORDER BY {_PRIORITY_ORDER} ASC, timestamp ASC LIMIT ?""",
            (str(telegram_id), limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_employees():
    with _conn() as con:
        rows = con.execute("""
            SELECT employee_name, employee_dept, COUNT(*) as total,
                   MAX(timestamp) as last_seen
            FROM classifications
            GROUP BY employee_name
            ORDER BY total DESC
        """).fetchall()
    return [dict(r) for r in rows]


def get_employee_stats(name: str) -> dict:
    with _conn() as con:
        rows = con.execute("""
            SELECT * FROM classifications
            WHERE employee_name = ?
            ORDER BY timestamp DESC
        """, (name,)).fetchall()

    if not rows:
        return {}

    records = [dict(r) for r in rows]

    tipo_counts = {}
    missing_room_count = 0
    all_missing = []
    low_confidence = 0

    for r in records:
        tipo_counts[r["tipo"]] = tipo_counts.get(r["tipo"], 0) + 1
        cf = json.loads(r["campos_faltantes"] or "[]")
        all_missing.extend(cf)
        if any("habitaci" in f.lower() or "room" in f.lower() or "ubicaci" in f.lower() for f in cf):
            missing_room_count += 1
        if r["confianza"] and r["confianza"] < 0.8:
            low_confidence += 1

    missing_counts = {}
    for f in all_missing:
        missing_counts[f] = missing_counts.get(f, 0) + 1
    top_missing = sorted(missing_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "name": name,
        "total": len(records),
        "tipo_counts": tipo_counts,
        "missing_room_pct": round(missing_room_count / len(records) * 100),
        "top_missing": top_missing,
        "low_confidence_pct": round(low_confidence / len(records) * 100),
        "last_seen": records[0]["timestamp"],
        "recent": records[:10],
    }


def get_all_history():
    with _conn() as con:
        rows = con.execute("""
            SELECT timestamp, employee_name, employee_dept, message,
                   tipo, prioridad, confianza, descripcion
            FROM classifications
            ORDER BY timestamp DESC
            LIMIT 200
        """).fetchall()
    return [dict(r) for r in rows]
