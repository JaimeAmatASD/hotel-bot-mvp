"""Versioned migrations. Apply with apply_pending() at startup.

To add a migration: append `(version, sql_or_callable)` to MIGRATIONS and bump
the version number. Migrations run in order, only if not already applied,
tracked in the `schema_meta` table.
"""
import logging
from typing import Callable, Union

from storage._conn import _conn

logger = logging.getLogger(__name__)

Migration = tuple[int, Union[str, Callable]]

def _rename_abierta_to_nueva(con) -> None:
    con.execute("UPDATE classifications SET estado='NUEVA' WHERE estado='ABIERTA'")


def _backfill_employee_telegram_id(con) -> None:
    """Rellena employee_telegram_id en las filas viejas usando otra fila del mismo nombre.

    La columna se agregó después de que ya hubiera datos, así que quedaron filas en NULL.
    Sin esto, mover la consulta de informes a telegram_id las volvería invisibles.
    Si un nombre no tiene ninguna fila con id, queda NULL: preferimos un hueco a un id inventado.
    """
    con.execute("""
        UPDATE classifications
           SET employee_telegram_id = (
               SELECT c2.employee_telegram_id
                 FROM classifications c2
                WHERE c2.employee_name = classifications.employee_name
                  AND c2.employee_telegram_id IS NOT NULL
                LIMIT 1)
         WHERE employee_telegram_id IS NULL
    """)


def _one_report_per_employee_per_day(con) -> None:
    """Agrega reports.report_date y garantiza un informe por empleado por día.

    Fusiona primero los duplicados históricos: sin eso el índice único falla y el bot
    no arranca. Sobrevive el informe de id menor (el primero del día); absorbe los ítems
    de los otros y se queda con el closed_at más tardío.
    """
    cols = {r[1] for r in con.execute("PRAGMA table_info(reports)")}
    if "report_date" not in cols:
        con.execute("ALTER TABLE reports ADD COLUMN report_date TEXT")

    # El índice puede existir ya (schema.py lo crea en bases nuevas) y bloquearía el
    # UPDATE de abajo: poblar report_date pasa necesariamente por un estado intermedio
    # con duplicados, que son justamente los que venimos a fusionar.
    con.execute("DROP INDEX IF EXISTS idx_reports_employee_day")

    con.execute("""
        UPDATE reports SET report_date = date(COALESCE(closed_at, started_at))
         WHERE report_date IS NULL
    """)

    duplicados = con.execute("""
        SELECT employee_telegram_id, report_date, MIN(id) AS keep_id
          FROM reports
         GROUP BY employee_telegram_id, report_date
        HAVING COUNT(*) > 1
    """).fetchall()

    for tid, fecha, keep_id in duplicados:
        con.execute("""UPDATE reports SET closed_at = (
                           SELECT MAX(closed_at) FROM reports
                            WHERE employee_telegram_id IS ? AND report_date = ?)
                        WHERE id = ?""", (tid, fecha, keep_id))
        con.execute("""UPDATE classifications SET report_id = ?
                        WHERE report_id IN (SELECT id FROM reports
                                             WHERE employee_telegram_id IS ? AND report_date = ?
                                               AND id != ?)""", (keep_id, tid, fecha, keep_id))
        con.execute("""DELETE FROM reports
                        WHERE employee_telegram_id IS ? AND report_date = ? AND id != ?""",
                    (tid, fecha, keep_id))

    con.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_reports_employee_day
                   ON reports(employee_telegram_id, report_date)""")


MIGRATIONS: list[Migration] = [
    (1, _rename_abierta_to_nueva),
    (2, _backfill_employee_telegram_id),
    (3, _one_report_per_employee_per_day),
]


def _ensure_meta_table(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS schema_meta (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """)


def _applied_versions(con) -> set[int]:
    return {row[0] for row in con.execute("SELECT version FROM schema_meta").fetchall()}


def apply_pending() -> None:
    """Apply pending migrations. Idempotent."""
    with _conn() as con:
        _ensure_meta_table(con)
        applied = _applied_versions(con)
        for version, op in MIGRATIONS:
            if version in applied:
                continue
            if callable(op):
                op(con)
            else:
                con.execute(op)
            con.execute(
                "INSERT INTO schema_meta (version, applied_at) VALUES (?, datetime('now'))",
                (version,),
            )
            logger.info(f"migrations: applied v{version}")
