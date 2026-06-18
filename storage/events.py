"""Event log + atomic state transitions.

`update_incident_state_atomic` uses BEGIN IMMEDIATE manual transaction control,
so it talks to sqlite3 directly (not via _conn) to manage isolation_level.
"""
import json
import sqlite3
from datetime import datetime

from config.enums import IncidentState
from storage._conn import DB_PATH, _conn


_ACTION_FROM_STATE = {
    IncidentState.ASIGNADA: "asignar",
    IncidentState.EN_PROCESO: "comenzar",
    IncidentState.RESUELTA: "terminado",
    IncidentState.CERRADA: "validar",
    IncidentState.CANCELADA: "cancelar",
}


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
    action: str | None = None,
    assignee_telegram_id: int | None = None,
    cancel_reason: str | None = None,
) -> dict:
    """Atomic read-modify-write usando BEGIN IMMEDIATE. Registra el evento en la misma transacción.

    `action` es el verbo (tomar/asignar/reasignar/reabrir/comenzar/terminado/validar/cancelar)
    y determina los campos de trazabilidad a escribir. Si no se pasa, se infiere del estado.
    """
    # Read DB_PATH dynamically so tests that patch storage.DB_PATH work.
    import storage
    actor_tid = actor.get("telegram_id", 0)
    actor_name = actor.get("nombre")
    actor_role = actor.get("rol", "EMPLEADO")
    action_name = action or _ACTION_FROM_STATE.get(new_state, str(new_state).lower())

    db_path = storage.DB_PATH
    db_path.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(str(db_path))
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

        current = row["estado"] or IncidentState.NUEVA
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

        if new_state == IncidentState.ASIGNADA and action_name == "reabrir":
            # Reabrir: solo cambia estado, conserva el asignado.
            con.execute("UPDATE classifications SET estado=? WHERE id=?",
                        (IncidentState.ASIGNADA, incident_id))
        elif new_state == IncidentState.ASIGNADA:
            assign_id = assignee_telegram_id or actor_tid
            con.execute(
                "UPDATE classifications SET estado=?, assigned_to_telegram_id=?, "
                "assigned_at=?, assigned_by=? WHERE id=?",
                (IncidentState.ASIGNADA, assign_id, now, actor_tid, incident_id),
            )
        elif new_state == IncidentState.EN_PROCESO:
            assign_id = row["assigned_to_telegram_id"] or actor_tid
            con.execute(
                "UPDATE classifications SET estado=?, assigned_to_telegram_id=?, "
                "assigned_at=COALESCE(assigned_at, ?) WHERE id=?",
                (IncidentState.EN_PROCESO, assign_id, now, incident_id),
            )
        elif new_state == IncidentState.RESUELTA:
            con.execute(
                "UPDATE classifications SET estado=?, resolved_by=?, resolved_at=? WHERE id=?",
                (IncidentState.RESUELTA, actor_tid, now, incident_id),
            )
        elif new_state == IncidentState.CERRADA:
            try:
                created_dt = datetime.fromisoformat(row["timestamp"])
                resolution_minutes = int((datetime.now() - created_dt).total_seconds() / 60)
            except Exception:
                resolution_minutes = None
            con.execute(
                "UPDATE classifications SET estado=?, closed_at=?, closed_by=?, "
                "resolution_time_minutes=? WHERE id=?",
                (IncidentState.CERRADA, now, actor_tid, resolution_minutes, incident_id),
            )
        elif new_state == IncidentState.CANCELADA:
            con.execute(
                "UPDATE classifications SET estado=?, cancelled_by=?, cancel_reason=? WHERE id=?",
                (IncidentState.CANCELADA, actor_tid, cancel_reason, incident_id),
            )

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
    from storage.classifications import get_incident
    incident = get_incident(incident_id)
    if not incident:
        return None
    incident["events"] = get_events_for_incident(incident_id)
    return incident
