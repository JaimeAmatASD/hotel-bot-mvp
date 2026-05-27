"""Database connection helper.

DB_PATH lives here as the canonical value but is also re-exported via
`storage.DB_PATH`. `_conn()` reads it dynamically from the storage package
namespace so tests that patch `storage.DB_PATH` work transparently.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "hotel_bot.db"


def _conn():
    # Read DB_PATH dynamically from the storage package — supports patch.object(storage, "DB_PATH", ...).
    import storage
    db_path = getattr(storage, "DB_PATH", DB_PATH)
    db_path.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con
