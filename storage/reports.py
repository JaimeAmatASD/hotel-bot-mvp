"""Shift reports: create, link classifications, fetch recent for employee."""
from datetime import datetime, timedelta
from storage._conn import _conn


def create_report(employee: dict) -> int:
    """Inserts a closed report record and returns its id. Draft state lives only in user_data."""
    tid = employee.get("telegram_id", 0)
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO reports (employee_telegram_id, employee_name, employee_department, started_at, closed_at, status)
               VALUES (?,?,?,?,?,?)""",
            (tid, employee.get("nombre"), employee.get("departamento"), now, now, "CLOSED"),
        )
        return cur.lastrowid


def get_report_with_items(report_id: int) -> dict | None:
    """Returns report dict with linked classification items. `messages` is always [] (legacy)."""
    with _conn() as con:
        row = con.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if not row:
        return None
    report = dict(row)
    report["messages"] = []
    with _conn() as con:
        items = con.execute(
            "SELECT * FROM classifications WHERE report_id = ? ORDER BY timestamp ASC",
            (report_id,),
        ).fetchall()
    report["items"] = [dict(r) for r in items]
    return report


def link_classification_to_report(classification_id: int, report_id: int) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE classifications SET report_id = ? WHERE id = ?",
            (report_id, classification_id),
        )


def link_classifications_to_report(classification_ids: list[int], report_id: int) -> None:
    if not classification_ids:
        return
    placeholders = ",".join("?" * len(classification_ids))
    with _conn() as con:
        con.execute(
            f"UPDATE classifications SET report_id = ? WHERE id IN ({placeholders})",
            [report_id, *classification_ids],
        )


def get_classifications_for_employee_recent(
    employee_name: str,
    hours: int,
    exclude_in_report: bool = True,
) -> list[dict]:
    """Returns classifications for an employee in the last N hours, excluding NO_REPORTE and ERROR."""
    since = (datetime.now() - timedelta(hours=hours)).isoformat(timespec="seconds")
    query = """
        SELECT * FROM classifications
        WHERE employee_name = ?
          AND timestamp >= ?
          AND tipo NOT IN ('NO_REPORTE', 'ERROR')
    """
    params: list = [employee_name, since]
    if exclude_in_report:
        query += " AND report_id IS NULL"
    query += " ORDER BY timestamp ASC"
    with _conn() as con:
        rows = con.execute(query, params).fetchall()
    return [dict(r) for r in rows]


_ESTADOS_TERMINALES = ("CERRADA", "CANCELADA")


def get_classifications_for_employee_day(telegram_id: int, day: str) -> list[dict]:
    """Ítems del empleado en un día calendario (YYYY-MM-DD).

    A diferencia de get_classifications_for_employee_recent, NO filtra por report_id:
    ese filtro es lo que hacía que un ítem ya consolidado desapareciera para siempre.
    """
    with _conn() as con:
        rows = con.execute(
            """SELECT * FROM classifications
                WHERE employee_telegram_id = ?
                  AND date(timestamp) = ?
                  AND tipo NOT IN ('NO_REPORTE', 'ERROR')
                ORDER BY timestamp ASC""",
            (telegram_id, day),
        ).fetchall()
    return [dict(r) for r in rows]


def get_open_incidents_before_day(telegram_id: int, day: str) -> list[dict]:
    """Incidencias que reportó esta persona ANTES de `day` y siguen sin cerrarse.

    Es el arrastre: se muestra en el informe de hoy pero no se re-linkea, porque cada
    ítem pertenece al informe del día en que se cargó. El criterio es "sigue sin
    resolverse", no "nunca se consolidó", así que no filtra por report_id.
    Van de más vieja a más nueva: la plantilla muestra solo las primeras.
    """
    placeholders = ",".join("?" * len(_ESTADOS_TERMINALES))
    with _conn() as con:
        rows = con.execute(
            f"""SELECT * FROM classifications
                 WHERE employee_telegram_id = ?
                   AND date(timestamp) < ?
                   AND tipo = 'INCIDENCIA'
                   AND COALESCE(estado, 'NUEVA') NOT IN ({placeholders})
                 ORDER BY timestamp ASC""",
            (telegram_id, day, *_ESTADOS_TERMINALES),
        ).fetchall()
    return [dict(r) for r in rows]


def get_classifications_recent(hours: int) -> list[dict]:
    """Todas las clasificaciones en las últimas N horas (excluye NO_REPORTE/ERROR),
    de cualquier empleado y sin importar si ya están en un reporte. Solo lectura."""
    since = (datetime.now() - timedelta(hours=hours)).isoformat(timespec="seconds")
    with _conn() as con:
        rows = con.execute(
            """SELECT * FROM classifications
               WHERE timestamp >= ?
                 AND tipo NOT IN ('NO_REPORTE', 'ERROR')
               ORDER BY timestamp ASC""",
            (since,),
        ).fetchall()
    return [dict(r) for r in rows]
