import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "hotel_bot.db"


def _conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS classifications (
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
                descripcion      TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                telegram_id INTEGER PRIMARY KEY,
                debug_mode  INTEGER DEFAULT 0
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id                           INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp                    TEXT NOT NULL,
                incident_id                  INTEGER NOT NULL,
                recipient_telegram_id        INTEGER NOT NULL,
                recipient_actual_telegram_id INTEGER NOT NULL,
                redirect_mode                TEXT,
                status                       TEXT NOT NULL,
                error_message                TEXT,
                FOREIGN KEY (incident_id) REFERENCES classifications(id)
            )
        """)
        # Add photo_path column if missing (migration for existing DBs)
        cols = [row[1] for row in con.execute("PRAGMA table_info(classifications)").fetchall()]
        if "photo_path" not in cols:
            con.execute("ALTER TABLE classifications ADD COLUMN photo_path TEXT")
        # Migrations for user_preferences notification columns
        pref_cols = [row[1] for row in con.execute("PRAGMA table_info(user_preferences)").fetchall()]
        if "notification_mode" not in pref_cols:
            con.execute("ALTER TABLE user_preferences ADD COLUMN notification_mode TEXT DEFAULT 'criticas'")
        if "excluded_departments" not in pref_cols:
            con.execute("ALTER TABLE user_preferences ADD COLUMN excluded_departments TEXT DEFAULT ''")


def get_debug_mode(telegram_id: int) -> bool:
    init_db()
    with _conn() as con:
        row = con.execute(
            "SELECT debug_mode FROM user_preferences WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
    return bool(row["debug_mode"]) if row else False


def set_debug_mode(telegram_id: int, enabled: bool) -> None:
    init_db()
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO user_preferences (telegram_id, debug_mode) VALUES (?, ?)",
            (telegram_id, int(enabled)),
        )


def save(employee: dict, message: str, result: dict) -> int:
    init_db()
    with _conn() as con:
        cur = con.execute("""
            INSERT INTO classifications
            (timestamp, employee_name, employee_dept, message, tipo, prioridad,
             categoria, ubicacion, confianza, campos_faltantes, habitacion,
             huesped_afectado, descripcion, photo_path)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            datetime.now().isoformat(timespec="seconds"),
            employee["nombre"],
            employee.get("departamento"),
            message,
            result.get("tipo"),
            result.get("prioridad"),
            result.get("categoria"),
            result.get("ubicacion"),
            result.get("confianza"),
            json.dumps(result.get("campos_faltantes", []), ensure_ascii=False),
            result.get("habitacion_huesped"),
            int(result.get("huesped_afectado") or 0),
            result.get("descripcion"),
            result.get("_meta", {}).get("photo_path"),
        ))
        return cur.lastrowid


def get_employees():
    init_db()
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
    init_db()
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
    init_db()
    with _conn() as con:
        rows = con.execute("""
            SELECT timestamp, employee_name, employee_dept, message,
                   tipo, prioridad, confianza, descripcion
            FROM classifications
            ORDER BY timestamp DESC
            LIMIT 200
        """).fetchall()
    return [dict(r) for r in rows]


_DISPLAY_PREFIXES = {
    "INCIDENCIA": "INC",
    "OBSERVACION": "OBS",
    "GUEST_INTEL": "MEM",
    "NO_REPORTE": "NR",
}


def generate_display_id(tipo: str, id: int) -> str:
    prefix = _DISPLAY_PREFIXES.get(tipo, "??")
    return f"{prefix}-{id:03d}"


def save_notification(
    incident_id: int,
    recipient_telegram_id: int,
    recipient_actual_telegram_id: int,
    redirect_mode: str,
    status: str,
    error_message: str | None = None,
) -> None:
    init_db()
    with _conn() as con:
        con.execute("""
            INSERT INTO notifications
            (timestamp, incident_id, recipient_telegram_id, recipient_actual_telegram_id,
             redirect_mode, status, error_message)
            VALUES (?,?,?,?,?,?,?)
        """, (
            datetime.now().isoformat(timespec="seconds"),
            incident_id,
            recipient_telegram_id,
            recipient_actual_telegram_id,
            redirect_mode,
            status,
            error_message,
        ))


def get_notifications_for_incident(incident_id: int) -> list[dict]:
    init_db()
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM notifications WHERE incident_id = ? ORDER BY timestamp",
            (incident_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_recent_notifications(limit: int = 50) -> list[dict]:
    init_db()
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM notifications ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_notification_preferences(telegram_id: int) -> dict:
    """Returns {"mode": "criticas", "excluded_departments": [...]}"""
    init_db()
    with _conn() as con:
        row = con.execute(
            "SELECT notification_mode, excluded_departments FROM user_preferences WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()
    if not row:
        return {"mode": "criticas", "excluded_departments": []}
    excluded_raw = row["excluded_departments"] or ""
    excluded = [d.strip() for d in excluded_raw.split(",") if d.strip()]
    return {"mode": row["notification_mode"] or "criticas", "excluded_departments": excluded}


def set_notification_mode(telegram_id: int, mode: str) -> None:
    init_db()
    with _conn() as con:
        con.execute(
            """INSERT INTO user_preferences (telegram_id, notification_mode)
               VALUES (?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET notification_mode = excluded.notification_mode""",
            (telegram_id, mode),
        )


def toggle_excluded_department(telegram_id: int, departamento: str) -> bool:
    """Toggle: si estaba excluido lo quita, si no lo agrega. Devuelve True si quedó excluido."""
    prefs = get_notification_preferences(telegram_id)
    excluded = prefs["excluded_departments"]
    dept_upper = departamento.upper()
    if dept_upper in excluded:
        excluded.remove(dept_upper)
        is_excluded = False
    else:
        excluded.append(dept_upper)
        is_excluded = True
    with _conn() as con:
        con.execute(
            """INSERT INTO user_preferences (telegram_id, excluded_departments)
               VALUES (?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET excluded_departments = excluded.excluded_departments""",
            (telegram_id, ",".join(excluded)),
        )
    return is_excluded
