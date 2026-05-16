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
        # incident_events table (append-only audit log)
        con.execute("""
            CREATE TABLE IF NOT EXISTS incident_events (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp           TEXT NOT NULL,
                incident_id         INTEGER NOT NULL,
                actor_telegram_id   INTEGER NOT NULL,
                actor_name          TEXT,
                actor_role          TEXT,
                action              TEXT NOT NULL,
                from_state          TEXT,
                to_state            TEXT,
                success             INTEGER NOT NULL DEFAULT 1,
                reason              TEXT,
                extra               TEXT,
                FOREIGN KEY (incident_id) REFERENCES classifications(id)
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_events_incident ON incident_events(incident_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON incident_events(timestamp)")
        # Migrations for incident state tracking
        cls_cols = [row[1] for row in con.execute("PRAGMA table_info(classifications)").fetchall()]
        for col, default in [
            ("estado", "ABIERTA"),
            ("assigned_to_telegram_id", None),
            ("assigned_at", None),
            ("closed_at", None),
            ("resolution_time_minutes", None),
        ]:
            if col not in cls_cols:
                suffix = f" DEFAULT '{default}'" if default else ""
                con.execute(f"ALTER TABLE classifications ADD COLUMN {col} TEXT{suffix}")


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


def get_incident(incident_id: int) -> dict | None:
    init_db()
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM classifications WHERE id = ?", (incident_id,)
        ).fetchone()
    return dict(row) if row else None


def update_incident_state(
    incident_id: int,
    new_state: str,
    actor_telegram_id: int,
) -> dict:
    """Aplica transición de estado. Devuelve {success, new_state, reason}."""
    init_db()
    with _conn() as con:
        row = con.execute(
            "SELECT estado, assigned_to_telegram_id, timestamp FROM classifications WHERE id = ?",
            (incident_id,),
        ).fetchone()
    if not row:
        return {"success": False, "new_state": None, "reason": "Incidencia no encontrada"}

    current = row["estado"] or "ABIERTA"

    # Transition validity: states that cannot be reached from the current one
    invalid = {
        "ASIGNADA":   {"ASIGNADA"},
        "EN_PROCESO": {"ASIGNADA", "EN_PROCESO"},
        "CERRADA":    {"ASIGNADA", "EN_PROCESO", "CERRADA"},
    }
    blocked = invalid.get(current, set())
    if new_state in blocked:
        return {
            "success": False,
            "new_state": current,
            "reason": f"La incidencia ya está en estado {current}",
        }

    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as con:
        if new_state == "ASIGNADA":
            con.execute(
                "UPDATE classifications SET estado=?, assigned_to_telegram_id=?, assigned_at=? WHERE id=?",
                ("ASIGNADA", actor_telegram_id, now, incident_id),
            )
        elif new_state == "EN_PROCESO":
            # Assign actor if not already assigned
            assign_id = row["assigned_to_telegram_id"] or actor_telegram_id
            assign_at = now if not row["assigned_to_telegram_id"] else None
            if assign_at:
                con.execute(
                    "UPDATE classifications SET estado=?, assigned_to_telegram_id=?, assigned_at=? WHERE id=?",
                    ("EN_PROCESO", assign_id, assign_at, incident_id),
                )
            else:
                con.execute(
                    "UPDATE classifications SET estado=? WHERE id=?",
                    ("EN_PROCESO", incident_id),
                )
        elif new_state == "CERRADA":
            created_at = row["timestamp"]
            try:
                created_dt = datetime.fromisoformat(created_at)
                resolution_minutes = int((datetime.now() - created_dt).total_seconds() / 60)
            except Exception:
                resolution_minutes = None
            con.execute(
                "UPDATE classifications SET estado=?, closed_at=?, resolution_time_minutes=? WHERE id=?",
                ("CERRADA", now, resolution_minutes, incident_id),
            )

    return {"success": True, "new_state": new_state, "reason": None}


def get_incident_assignee(incident_id: int) -> dict | None:
    init_db()
    with _conn() as con:
        row = con.execute(
            "SELECT assigned_to_telegram_id FROM classifications WHERE id = ?",
            (incident_id,),
        ).fetchone()
    if not row or not row["assigned_to_telegram_id"]:
        return None
    return {"telegram_id": row["assigned_to_telegram_id"]}


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


_PRIORITY_ORDER = "CASE prioridad WHEN 'CRITICA' THEN 1 WHEN 'ALTA' THEN 2 WHEN 'MEDIA' THEN 3 WHEN 'BAJA' THEN 4 ELSE 5 END"


def get_open_incidents(prioridad: str | None = None, limit: int = 100) -> list[dict]:
    init_db()
    params: list = []
    where = "tipo = 'INCIDENCIA' AND (estado IS NULL OR estado IN ('ABIERTA', 'ASIGNADA', 'EN_PROCESO'))"
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


def get_incidents_for_room(room_or_zone: str, days_back: int = 30) -> list[dict]:
    init_db()
    since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    since -= timedelta(days=days_back)
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
    init_db()
    from datetime import timedelta
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
    init_db()
    from datetime import timedelta
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
    init_db()
    from datetime import timedelta
    since = (datetime.now() - timedelta(days=days_back)).isoformat(timespec="seconds")
    pattern = f"%{query}%"
    with _conn() as con:
        rows = con.execute(
            """SELECT * FROM classifications
               WHERE timestamp >= ?
                 AND (LOWER(message) LIKE LOWER(?)
                   OR LOWER(descripcion) LIKE LOWER(?)
                   OR LOWER(ubicacion) LIKE LOWER(?))
               ORDER BY timestamp DESC
               LIMIT ?""",
            (since, pattern, pattern, pattern, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Event log
# ---------------------------------------------------------------------------

_ACTION_FROM_STATE = {"ASIGNADA": "tomar", "EN_PROCESO": "en_proceso", "CERRADA": "cerrar"}


def save_event(
    incident_id: int,
    actor_telegram_id: int,
    action: str,
    actor_name: str | None = None,
    actor_role: str | None = None,
    from_state: str | None = None,
    to_state: str | None = None,
    success: bool = True,
    reason: str | None = None,
    extra: dict | None = None,
) -> int:
    init_db()
    extra_json = json.dumps(extra, ensure_ascii=False) if extra else None
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO incident_events
               (timestamp, incident_id, actor_telegram_id, actor_name, actor_role,
                action, from_state, to_state, success, reason, extra)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                datetime.now().isoformat(timespec="seconds"),
                incident_id, actor_telegram_id, actor_name, actor_role,
                action, from_state, to_state, int(success), reason, extra_json,
            ),
        )
        return cur.lastrowid


def get_events_for_incident(incident_id: int) -> list[dict]:
    init_db()
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM incident_events WHERE incident_id = ? ORDER BY timestamp ASC, id ASC",
            (incident_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        if d.get("extra"):
            try:
                d["extra"] = json.loads(d["extra"])
            except Exception:
                pass
        result.append(d)
    return result


def update_incident_state_atomic(
    incident_id: int,
    new_state: str,
    actor: dict,
    expected_from_states: list[str],
) -> dict:
    """Atomic read-modify-write using BEGIN IMMEDIATE. Registers event in same transaction."""
    init_db()
    actor_tid = actor.get("telegram_id", 0)
    actor_name = actor.get("nombre")
    actor_role = actor.get("rol", "EMPLEADO")
    action_name = _ACTION_FROM_STATE.get(new_state, new_state.lower())

    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    con.isolation_level = None  # manual transaction control
    try:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT estado, assigned_to_telegram_id, timestamp FROM classifications WHERE id = ?",
            (incident_id,),
        ).fetchone()

        if not row:
            con.execute("ROLLBACK")
            return {"success": False, "from_state": None, "to_state": None, "reason": "Incidencia no encontrada"}

        current = row["estado"] or "ABIERTA"
        now = datetime.now().isoformat(timespec="seconds")

        if current not in expected_from_states:
            con.execute(
                """INSERT INTO incident_events
                   (timestamp, incident_id, actor_telegram_id, actor_name, actor_role,
                    action, from_state, to_state, success, reason)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (now, incident_id, actor_tid, actor_name, actor_role,
                 "action_rejected_already_done", current, None, 0,
                 f"La incidencia ya está en estado {current}"),
            )
            con.execute("COMMIT")
            return {
                "success": False,
                "from_state": current,
                "to_state": current,
                "reason": f"La incidencia ya está en estado {current}",
            }

        # Apply the state transition
        if new_state == "ASIGNADA":
            con.execute(
                "UPDATE classifications SET estado=?, assigned_to_telegram_id=?, assigned_at=? WHERE id=?",
                ("ASIGNADA", actor_tid, now, incident_id),
            )
        elif new_state == "EN_PROCESO":
            assign_id = row["assigned_to_telegram_id"] or actor_tid
            if not row["assigned_to_telegram_id"]:
                con.execute(
                    "UPDATE classifications SET estado=?, assigned_to_telegram_id=?, assigned_at=? WHERE id=?",
                    ("EN_PROCESO", assign_id, now, incident_id),
                )
            else:
                con.execute("UPDATE classifications SET estado=? WHERE id=?", ("EN_PROCESO", incident_id))
        elif new_state == "CERRADA":
            try:
                created_dt = datetime.fromisoformat(row["timestamp"])
                resolution_minutes = int((datetime.now() - created_dt).total_seconds() / 60)
            except Exception:
                resolution_minutes = None
            con.execute(
                "UPDATE classifications SET estado=?, closed_at=?, resolution_time_minutes=? WHERE id=?",
                ("CERRADA", now, resolution_minutes, incident_id),
            )

        # Register success event
        con.execute(
            """INSERT INTO incident_events
               (timestamp, incident_id, actor_telegram_id, actor_name, actor_role,
                action, from_state, to_state, success)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (now, incident_id, actor_tid, actor_name, actor_role,
             action_name, current, new_state, 1),
        )
        con.execute("COMMIT")
        return {"success": True, "from_state": current, "to_state": new_state, "reason": None}

    except Exception as e:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        return {"success": False, "from_state": None, "to_state": None, "reason": str(e)}
    finally:
        con.close()


def get_incident_with_events(incident_id: int) -> dict | None:
    incident = get_incident(incident_id)
    if not incident:
        return None
    incident["events"] = get_events_for_incident(incident_id)
    return incident
