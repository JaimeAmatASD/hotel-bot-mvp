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


MIGRATIONS: list[Migration] = [
    (1, _rename_abierta_to_nueva),
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
