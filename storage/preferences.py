"""User preferences: debug mode, notification mode, excluded departments."""
from storage._conn import _conn


def get_debug_mode(telegram_id: int) -> bool:
    with _conn() as con:
        row = con.execute(
            "SELECT debug_mode FROM user_preferences WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
    return bool(row["debug_mode"]) if row else False


def set_debug_mode(telegram_id: int, enabled: bool) -> None:
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO user_preferences (telegram_id, debug_mode) VALUES (?, ?)",
            (telegram_id, int(enabled)),
        )


def get_notification_preferences(telegram_id: int) -> dict:
    """Returns {"mode": "criticas", "excluded_departments": [...]}."""
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
