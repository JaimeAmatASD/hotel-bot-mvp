"""Schema definition + ALTER TABLE migrations applied idempotently."""
from storage._conn import _conn


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
                subcategoria     TEXT,
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
        cols = [row[1] for row in con.execute("PRAGMA table_info(classifications)").fetchall()]
        if "photo_path" not in cols:
            con.execute("ALTER TABLE classifications ADD COLUMN photo_path TEXT")
        if "employee_telegram_id" not in cols:
            con.execute("ALTER TABLE classifications ADD COLUMN employee_telegram_id INTEGER")
        if "subcategoria" not in cols:
            con.execute("ALTER TABLE classifications ADD COLUMN subcategoria TEXT")
        pref_cols = [row[1] for row in con.execute("PRAGMA table_info(user_preferences)").fetchall()]
        if "notification_mode" not in pref_cols:
            con.execute("ALTER TABLE user_preferences ADD COLUMN notification_mode TEXT DEFAULT 'criticas'")
        if "excluded_departments" not in pref_cols:
            con.execute("ALTER TABLE user_preferences ADD COLUMN excluded_departments TEXT DEFAULT ''")
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
        con.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_telegram_id INTEGER NOT NULL,
                employee_name        TEXT,
                employee_department  TEXT,
                started_at           TEXT NOT NULL,
                closed_at            TEXT,
                closure_type         TEXT,
                status               TEXT NOT NULL,
                report_date          TEXT
            )
        """)
        # CREATE TABLE IF NOT EXISTS es no-op sobre una base que ya existe, así que la
        # columna hay que agregarla aparte antes de indexarla.
        report_cols = [row[1] for row in con.execute("PRAGMA table_info(reports)").fetchall()]
        if "report_date" not in report_cols:
            con.execute("ALTER TABLE reports ADD COLUMN report_date TEXT")
        # Un informe por empleado por día. La garantía vive acá, no en un if del handler.
        # Los duplicados históricos los fusiona la migración v3, que baja este índice primero.
        con.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_reports_employee_day
                ON reports(employee_telegram_id, report_date)
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS report_messages (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id    INTEGER NOT NULL,
                timestamp    TEXT NOT NULL,
                message_type TEXT NOT NULL,
                content      TEXT,
                photo_path   TEXT,
                FOREIGN KEY (report_id) REFERENCES reports(id)
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_reports_employee ON reports(employee_telegram_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_report_messages_report ON report_messages(report_id)")
        cls_cols2 = [row[1] for row in con.execute("PRAGMA table_info(classifications)").fetchall()]
        if "report_id" not in cls_cols2:
            con.execute("ALTER TABLE classifications ADD COLUMN report_id INTEGER REFERENCES reports(id)")
        cls_cols = [row[1] for row in con.execute("PRAGMA table_info(classifications)").fetchall()]
        for col, default in [
            ("estado", "NUEVA"),
            ("assigned_to_telegram_id", None),
            ("assigned_at", None),
            ("assigned_by", None),
            ("resolved_by", None),
            ("resolved_at", None),
            ("closed_at", None),
            ("closed_by", None),
            ("cancelled_by", None),
            ("cancel_reason", None),
            ("resolution_time_minutes", None),
        ]:
            if col not in cls_cols:
                suffix = f" DEFAULT '{default}'" if default else ""
                con.execute(f"ALTER TABLE classifications ADD COLUMN {col} TEXT{suffix}")
