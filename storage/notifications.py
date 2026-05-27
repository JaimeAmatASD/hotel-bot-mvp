"""Notifications log: per-incident audit of who got notified and when."""
from datetime import datetime
from storage._conn import _conn


def save_notification(
    incident_id: int,
    recipient_telegram_id: int,
    recipient_actual_telegram_id: int,
    redirect_mode: str,
    status: str,
    error_message: str | None = None,
) -> None:
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
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM notifications WHERE incident_id = ? ORDER BY timestamp",
            (incident_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_recent_notifications(limit: int = 50) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM notifications ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
