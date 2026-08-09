# Sprint C.1 — Rediseño del informe de turno

> **Para agentes:** SUB-SKILL REQUERIDO: usar `superpowers:subagent-driven-development` (recomendado) o
> `superpowers:executing-plans` para implementar tarea por tarea. Los pasos usan checkbox (`- [ ]`).

**Goal:** Que `/reporte` devuelva siempre la tira del día con los pendientes arriba, deje sumar un ítem
sin salir del flujo, y no vuelva a perder ítems en silencio.

**Architecture:** La ventana pasa de "últimas N horas" a día calendario, y desaparece el filtro
`report_id IS NULL` que era lo que comía ítems. La unicidad "un informe por persona por día" se
garantiza con un índice UNIQUE en la base, no con un `if` en el código. La identidad de consulta
migra de `employee_name` a `employee_telegram_id`, con backfill previo.

**Tech Stack:** Python 3.11, SQLite (`storage/`), python-telegram-bot v20+, gspread.

## Global Constraints

- Tests: `venv/bin/pytest -q` — la suite normal debe quedar verde (232 tests hoy, más los nuevos).
- Nada de magic strings: usar `config.enums` (`IncidentState`, `ReportType`, `Priority`, `Role`).
- SQLite es la única fuente de verdad. Sheets es espejo: si falla, no rompe nada.
- `storage.init_db()` se llama una sola vez al arranque. Los tests inicializan tras
  `patch.object(storage, "DB_PATH", ...)`.
- Un commit por tarea. TDD: test que falla → implementación mínima → test que pasa → commit.
- Formato de fecha-día en todo el sprint: string `YYYY-MM-DD` (lo que devuelve `date.today().isoformat()`).

## Decisiones ya tomadas (no re-litigar)

| Decisión | Valor |
|---|---|
| Ventana de `/reporte` | Día calendario (hoy 00:00 → ahora) |
| Pendientes de días anteriores | Se **muestran** como arrastre, **no** se re-linkean al informe de hoy |
| Re-ejecutar `/reporte` el mismo día | Actualiza el mismo REP-N (upsert), no crea uno nuevo |
| "Sumar algo" | Un ítem más por el flujo normal (clasificador), enganchado al día |
| Pendientes en Sheets | Dos columnas nuevas en la hoja `Reportes de turno` |
| `/reporte 6h` / `/reporte 24h` | **Se elimina** |
| Botón "✏️ Corregir un ítem" del informe | **Se elimina** (corregir sigue estando al cargar el ítem) |
| Los 16 ítems huérfanos históricos | No se tocan. Los 3 que siguen abiertos reaparecen solos como arrastre |

## Fuera de alcance (explícito)

- Turnos reales (fichar entrada/salida, handover que el turno siguiente recibe).
- Turnos nocturnos que cruzan medianoche: un turno que arranca 23:00 va a caer partido en dos días.
  Con 2 personas en piloto diurno no vale la pena; si aparece, se ataca con un `shift_date` propio.
- `/reporte sector` y `/reporte REP-N`: no se tocan.

## Estructura de archivos

| Archivo | Responsabilidad | Acción |
|---|---|---|
| `storage/schema.py` | `report_date` + índice único para bases nuevas | Modificar |
| `storage/migrations.py` | Migraciones v2 y v3 para la base existente | Modificar |
| `storage/reports.py` | Consultas por día + upsert del informe | Modificar |
| `report_processor.py` | Plantilla del informe | Modificar |
| `presenters/keyboards.py` | Teclado del borrador | Modificar |
| `handlers/command_handler.py` | `/reporte` sin args | Modificar |
| `handlers/callback_handler.py` | Confirmar / sumar algo | Modificar |
| `sheets_sync.py` | Columnas de pendientes + upsert | Modificar |
| `tests/test_migrations.py` | Tests de migración | Modificar |
| `tests/test_reports_day.py` | Tests de las consultas por día | Crear |
| `tests/test_report_template.py` | Tests de la plantilla | Crear |
| `tests/test_sheets_sync.py` | Tests del espejo | Modificar |
| `tests/test_hotel_scenarios.py` | E2E del flujo completo | Modificar |

---

## Task 1: Migraciones v2 y v3

**Contexto que el implementador necesita:** la base de producción es `data/hotel_bot.db`. Hoy tiene
39 `classifications` (19 con `employee_telegram_id` en NULL, porque la columna se agregó después) y
8 `reports`, de los cuales **REP-003 y REP-004 son los dos de Juan el 2026-07-01**. Ese duplicado
hace fallar el `CREATE UNIQUE INDEX` si no se fusiona primero, y un fallo ahí rompe el arranque del bot.

**Files:**
- Modify: `storage/schema.py:77-87` (CREATE TABLE reports)
- Modify: `storage/migrations.py`
- Test: `tests/test_migrations.py`

> **Por qué se tocan los dos:** `init_db()` **no** corre `apply_pending()` — las migraciones solo
> corren en `bot.py:79` al arrancar. Si `report_date` viviera solo en la migración, toda base nueva
> (o sea, cada test con `tmp_path`) quedaría sin la columna. `schema.py` cubre las bases nuevas;
> la migración cubre la base de producción que ya existe. Las dos son idempotentes, así que
> corren juntas sin pisarse.

**Interfaces:**
- Consumes: `storage._conn` (re-exportado en `storage/__init__.py`), `MIGRATIONS`, `apply_pending()`.
- Produces: tras `apply_pending()`, toda fila de `classifications` con un `employee_name` conocido tiene
  `employee_telegram_id`; `reports` tiene columna `report_date TEXT` poblada y un índice único
  `idx_reports_employee_day` sobre `(employee_telegram_id, report_date)`.

- [ ] **Step 1: Backup de la base antes de tocar nada**

```bash
mkdir -p data/backups
venv/bin/python -c "
import sqlite3
src = sqlite3.connect('data/hotel_bot.db')
dst = sqlite3.connect('data/backups/hotel_bot.pre-c1.db')
src.backup(dst); dst.close(); src.close()
print('backup ok')
"
ls -la data/backups/
```

Esperado: `hotel_bot.pre-c1.db` existe y pesa parecido al original.

- [ ] **Step 2: Escribir los tests que fallan**

En `tests/test_migrations.py`, agregar. **Seguí el idiom del archivo**: `tempfile.TemporaryDirectory()` +
`patch.object(storage, "DB_PATH", ...)` + `storage._conn()` (no `storage._conn._conn()` — `_conn`
está re-exportado en `storage/__init__.py`). Agregar `import sqlite3` y `import pytest` arriba.

```python
def test_v2_backfills_telegram_id_from_name():
    """Las filas viejas sin telegram_id lo heredan de otra fila con el mismo nombre."""
    with tempfile.TemporaryDirectory() as d:
        with patch.object(storage, "DB_PATH", Path(d) / "t.db"):
            storage.init_db()
            with storage._conn() as con:
                con.execute(
                    "INSERT INTO classifications (timestamp, employee_name, employee_telegram_id,"
                    " tipo, descripcion) VALUES"
                    " ('2026-07-01T10:00:00','Jaime A',7391337590,'INCIDENCIA','con id')")
                con.execute(
                    "INSERT INTO classifications (timestamp, employee_name, employee_telegram_id,"
                    " tipo, descripcion) VALUES"
                    " ('2026-06-01T10:00:00','Jaime A',NULL,'INCIDENCIA','sin id')")
            apply_pending()
            with storage._conn() as con:
                rows = con.execute(
                    "SELECT descripcion, employee_telegram_id FROM classifications"
                    " ORDER BY descripcion").fetchall()
    assert dict(rows) == {"con id": 7391337590, "sin id": 7391337590}


def test_v3_merges_same_day_duplicate_reports():
    """Dos informes del mismo empleado el mismo día se fusionan en el de id menor."""
    with tempfile.TemporaryDirectory() as d:
        with patch.object(storage, "DB_PATH", Path(d) / "t.db"):
            storage.init_db()
            with storage._conn() as con:
                for closed in ("2026-07-01T16:57:01", "2026-07-01T17:37:19"):
                    con.execute(
                        "INSERT INTO reports (employee_telegram_id, employee_name, started_at,"
                        " closed_at, status) VALUES (8709342265,'Juan',?,?,'CLOSED')",
                        (closed, closed))
                con.execute(
                    "INSERT INTO classifications (timestamp, employee_name, tipo, descripcion,"
                    " report_id) VALUES ('2026-07-01T16:00:00','Juan','INCIDENCIA','del primero',1)")
                con.execute(
                    "INSERT INTO classifications (timestamp, employee_name, tipo, descripcion,"
                    " report_id) VALUES ('2026-07-01T17:00:00','Juan','INCIDENCIA','del segundo',2)")
            apply_pending()
            with storage._conn() as con:
                ids = [r[0] for r in con.execute("SELECT id FROM reports ORDER BY id")]
                linked = [r[0] for r in con.execute(
                    "SELECT report_id FROM classifications ORDER BY timestamp")]
                fecha = con.execute("SELECT report_date FROM reports WHERE id=1").fetchone()[0]
                cerrado = con.execute("SELECT closed_at FROM reports WHERE id=1").fetchone()[0]
    assert ids == [1], "el duplicado debe desaparecer"
    assert linked == [1, 1], "los ítems de ambos quedan en el informe sobreviviente"
    assert fecha == "2026-07-01"
    assert cerrado == "2026-07-01T17:37:19", "gana el cierre más tardío"


def test_v3_unique_index_blocks_second_report_same_day():
    """Después de migrar, la base misma impide dos informes del mismo día."""
    with tempfile.TemporaryDirectory() as d:
        with patch.object(storage, "DB_PATH", Path(d) / "t.db"):
            storage.init_db()
            apply_pending()
            with storage._conn() as con:
                con.execute(
                    "INSERT INTO reports (employee_telegram_id, employee_name, started_at,"
                    " closed_at, status, report_date)"
                    " VALUES (1,'A','x','x','CLOSED','2026-08-09')")
            with pytest.raises(sqlite3.IntegrityError):
                with storage._conn() as con:
                    con.execute(
                        "INSERT INTO reports (employee_telegram_id, employee_name, started_at,"
                        " closed_at, status, report_date)"
                        " VALUES (1,'A','y','y','CLOSED','2026-08-09')")
```

- [ ] **Step 3: Correr los tests y verificar que fallan**

Run: `venv/bin/pytest tests/test_migrations.py -v`
Esperado: los tres nuevos FALLAN (`no such column: report_date`, y el de backfill con IDs distintos).

- [ ] **Step 4: Implementar — primero el esquema de bases nuevas**

En `storage/schema.py`, en el `CREATE TABLE IF NOT EXISTS reports` (línea 77), agregar la columna
al final y crear el índice justo después del bloque:

```python
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
        # Un informe por empleado por día. La garantía vive acá, no en un if del handler.
        con.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_reports_employee_day
                ON reports(employee_telegram_id, report_date)
        """)
```

- [ ] **Step 5: Implementar las migraciones (para la base que ya existe)**

En `storage/migrations.py`, agregar antes de `MIGRATIONS`:

```python
def _backfill_employee_telegram_id(con) -> None:
    """Rellena employee_telegram_id en las filas viejas usando otra fila del mismo nombre.

    La columna se agregó después de que ya hubiera datos, así que 19 filas quedaron en NULL.
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
```

Y extender la lista:

```python
MIGRATIONS: list[Migration] = [
    (1, _rename_abierta_to_nueva),
    (2, _backfill_employee_telegram_id),
    (3, _one_report_per_employee_per_day),
]
```

- [ ] **Step 6: Correr los tests y verificar que pasan**

Run: `venv/bin/pytest tests/test_migrations.py -v`
Esperado: PASS los tres.

Run: `venv/bin/pytest -q`
Esperado: verde. El índice único es nuevo para toda base de test: si algún test creaba dos informes
del mismo empleado el mismo día, ahora revienta con `IntegrityError`. Eso es la red funcionando —
actualizá ese test para usar `upsert_report_for_day` (Task 3) o empleados distintos.

- [ ] **Step 7: Correr la migración contra la base real y verificar a mano**

```bash
venv/bin/python -c "
import storage; from storage import migrations
storage.init_db(); migrations.apply_pending()
"
venv/bin/python -c "
import sqlite3
c = sqlite3.connect('data/hotel_bot.db')
print('sin telegram_id:', c.execute('SELECT COUNT(*) FROM classifications WHERE employee_telegram_id IS NULL').fetchone()[0])
print('reports:', c.execute('SELECT COUNT(*) FROM reports').fetchone()[0])
print('items de REP-003:', c.execute('SELECT COUNT(*) FROM classifications WHERE report_id=3').fetchone()[0])
"
```

Esperado exacto: `sin telegram_id: 0`, `reports: 7` (era 8, se fusionó uno),
`items de REP-003: 4` (tenía 1, absorbió los 3 de REP-004).

> **Nota manual, no automatizable:** REP-004 ya no existe en la base. Si la hoja
> `Reportes de turno` de Google Sheets tiene una fila `REP-004`, borrala a mano — es una sola fila.

- [ ] **Step 8: Commit**

```bash
git add storage/schema.py storage/migrations.py tests/test_migrations.py
git commit -m "fix(reportes): backfill de telegram_id y un informe por empleado por día

Las 19 filas previas a la columna employee_telegram_id quedaban invisibles al
mover la consulta de informes a telegram_id. La v3 fusiona REP-003/REP-004 (los
dos de Juan del 2026-07-01) antes de crear el índice único: sin fusionar, el
CREATE UNIQUE INDEX falla y el bot no arranca.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 2: Consultas por día

**Files:**
- Modify: `storage/reports.py`
- Test: `tests/test_reports_day.py` (crear)

**Interfaces:**
- Consumes: `storage._conn._conn`.
- Produces:
  - `get_classifications_for_employee_day(telegram_id: int, day: str) -> list[dict]`
  - `get_open_incidents_before_day(telegram_id: int, day: str) -> list[dict]`

  Ambas devuelven listas de dicts como las demás de `storage/reports.py`, ordenadas por `timestamp ASC`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_reports_day.py`. La fixture autouse copia el patrón de `isolated_db` en
`tests/test_hotel_scenarios.py:99`:

```python
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import storage


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    with patch.object(storage, "DB_PATH", tmp_path / "reports_day.db"):
        storage.init_db()
        yield


def _insert(con, **kw):
    campos = {"timestamp": "2026-08-09T10:00:00", "employee_name": "Jaime A",
              "employee_telegram_id": 111, "tipo": "INCIDENCIA", "descripcion": "algo",
              "estado": "NUEVA", "report_id": None}
    campos.update(kw)
    cols = ",".join(campos)
    ph = ",".join("?" * len(campos))
    con.execute(f"INSERT INTO classifications ({cols}) VALUES ({ph})", list(campos.values()))


def test_day_query_ignores_report_id():
    """Un ítem ya consolidado sigue apareciendo: ese filtro era el que comía ítems."""
    with storage._conn() as con:
        _insert(con, descripcion="ya en un informe", report_id=7)
        _insert(con, descripcion="suelto")
    items = storage.get_classifications_for_employee_day(111, "2026-08-09")
    assert {i["descripcion"] for i in items} == {"ya en un informe", "suelto"}


def test_day_query_is_scoped_to_the_day_and_person():
    with storage._conn() as con:
        _insert(con, descripcion="hoy")
        _insert(con, descripcion="ayer", timestamp="2026-08-08T23:59:59")
        _insert(con, descripcion="otro empleado", employee_telegram_id=222)
    items = storage.get_classifications_for_employee_day(111, "2026-08-09")
    assert [i["descripcion"] for i in items] == ["hoy"]


def test_day_query_excludes_no_reporte_and_error():
    with storage._conn() as con:
        _insert(con, descripcion="válido")
        _insert(con, descripcion="ruido", tipo="NO_REPORTE")
        _insert(con, descripcion="fallo", tipo="ERROR")
    items = storage.get_classifications_for_employee_day(111, "2026-08-09")
    assert [i["descripcion"] for i in items] == ["válido"]


def test_carryover_only_open_incidents_from_earlier_days():
    with storage._conn() as con:
        _insert(con, descripcion="vieja abierta", timestamp="2026-07-02T10:00:00", estado="NUEVA")
        _insert(con, descripcion="vieja asignada", timestamp="2026-07-06T10:00:00", estado="ASIGNADA")
        _insert(con, descripcion="vieja cerrada", timestamp="2026-07-06T11:00:00", estado="CERRADA")
        _insert(con, descripcion="vieja cancelada", timestamp="2026-07-06T12:00:00", estado="CANCELADA")
        _insert(con, descripcion="vieja observación", timestamp="2026-07-06T13:00:00",
                tipo="OBSERVACION", estado=None)
        _insert(con, descripcion="de hoy abierta", timestamp="2026-08-09T09:00:00", estado="NUEVA")
    arrastre = storage.get_open_incidents_before_day(111, "2026-08-09")
    assert [i["descripcion"] for i in arrastre] == ["vieja abierta", "vieja asignada"]
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `venv/bin/pytest tests/test_reports_day.py -v`
Esperado: FAIL con `AttributeError: module 'storage' has no attribute 'get_classifications_for_employee_day'`.

- [ ] **Step 3: Implementar**

En `storage/reports.py`, agregar al final:

```python
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
    ítem pertenece al informe del día en que se cargó.
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
```

Exportarlas en `storage/__init__.py` junto a las demás de `reports` (seguir el patrón que ya está ahí).

- [ ] **Step 4: Correr y verificar que pasan**

Run: `venv/bin/pytest tests/test_reports_day.py -v`
Esperado: PASS los cuatro.

- [ ] **Step 5: Commit**

```bash
git add storage/reports.py storage/__init__.py tests/test_reports_day.py
git commit -m "feat(reportes): consultas por día calendario y arrastre de pendientes

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 3: Upsert del informe del día

**Files:**
- Modify: `storage/reports.py`
- Test: `tests/test_reports_day.py`

**Interfaces:**
- Consumes: el índice `idx_reports_employee_day` de la Task 1.
- Produces: `upsert_report_for_day(employee: dict, day: str) -> int` — devuelve el id del informe
  de ese empleado para ese día, creándolo si no existe. Llamarla dos veces el mismo día devuelve
  el mismo id.

- [ ] **Step 1: Escribir el test que falla**

Agregar a `tests/test_reports_day.py`:

```python
EMPLEADO = {"telegram_id": 111, "nombre": "Jaime A", "departamento": "MANTENIMIENTO"}


def test_upsert_report_is_idempotent_per_day():
    primero = storage.upsert_report_for_day(EMPLEADO, "2026-08-09")
    segundo = storage.upsert_report_for_day(EMPLEADO, "2026-08-09")
    otro_dia = storage.upsert_report_for_day(EMPLEADO, "2026-08-10")
    assert primero == segundo, "el mismo día reusa el informe"
    assert otro_dia != primero
    with storage._conn() as con:
        assert con.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 2


def test_upsert_refreshes_closed_at():
    rid = storage.upsert_report_for_day(EMPLEADO, "2026-08-09")
    with storage._conn() as con:
        con.execute("UPDATE reports SET closed_at = '2026-08-09T08:00:00' WHERE id = ?", (rid,))
    storage.upsert_report_for_day(EMPLEADO, "2026-08-09")
    with storage._conn() as con:
        cerrado = con.execute("SELECT closed_at FROM reports WHERE id=?", (rid,)).fetchone()[0]
    assert cerrado > "2026-08-09T08:00:00"
```

> No hace falta llamar a `apply_pending()` acá: la Task 1 puso `report_date` y el índice único
> directamente en `storage/schema.py`, así que toda base nueva ya nace con los dos.

- [ ] **Step 2: Correr y verificar que falla**

Run: `venv/bin/pytest tests/test_reports_day.py -k upsert -v`
Esperado: FAIL con `AttributeError: ... 'upsert_report_for_day'`.

- [ ] **Step 3: Implementar**

En `storage/reports.py`:

```python
def upsert_report_for_day(employee: dict, day: str) -> int:
    """Devuelve el informe del empleado para ese día, creándolo si no existe.

    Reemplaza a create_report en el flujo de /reporte: volver a cerrar el informe del
    mismo día actualiza el que ya está en vez de crear un REP nuevo.
    """
    tid = employee.get("telegram_id", 0)
    ahora = datetime.now().isoformat(timespec="seconds")
    with _conn() as con:
        row = con.execute(
            "SELECT id FROM reports WHERE employee_telegram_id = ? AND report_date = ?",
            (tid, day),
        ).fetchone()
        if row:
            con.execute("UPDATE reports SET closed_at = ? WHERE id = ?", (ahora, row[0]))
            return row[0]
        cur = con.execute(
            """INSERT INTO reports (employee_telegram_id, employee_name, employee_department,
                                    started_at, closed_at, status, report_date)
               VALUES (?,?,?,?,?,?,?)""",
            (tid, employee.get("nombre"), employee.get("departamento"),
             ahora, ahora, "CLOSED", day),
        )
        return cur.lastrowid
```

Exportarla en `storage/__init__.py`.

> `create_report` queda en el módulo: `tests/test_save_estado.py` y otros la usan. No la borres
> en esta tarea — si al final del sprint no la usa nadie, se saca en un commit aparte.

- [ ] **Step 4: Correr y verificar que pasan**

Run: `venv/bin/pytest tests/test_reports_day.py -v`
Esperado: PASS los seis.

- [ ] **Step 5: Commit**

```bash
git add storage/reports.py storage/__init__.py tests/test_reports_day.py
git commit -m "feat(reportes): upsert_report_for_day — un informe por persona por día

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 4: Plantilla nueva

**Files:**
- Modify: `report_processor.py:101-137` (`render_shift_report`)
- Test: `tests/test_report_template.py` (crear)

**Interfaces:**
- Consumes: `presenters.constants.ESTADO_EMOJI`, `TIPO_EMOJI`; `presenters.format_location.shorten_room_label`;
  `storage.generate_display_id`.
- Produces: `render_shift_report(items, *, display_id, employee_name, department, carryover=(), closed_at=None) -> str`
  — el parámetro `carryover` es nuevo y opcional, así que los llamadores actuales
  (`format_report_summary`, `format_report_for_manager`, `/reporte REP-N`) siguen compilando.

**Render objetivo** (esto es lo que tiene que producir; los tests verifican las partes que importan):

```
📋 INFORME DE TURNO — REP-012
👤 Jaime A · MANTENIMIENTO
🕐 09/08 · 08:10–15:45 · 7 ítems

⚠️ QUEDA PENDIENTE (3)
• INC-018 · Hab 203 — La cerradura no cierra con tarjeta · ALTA · 🆕 NUEVA · ↩ 02/07
• INC-020 · Hab 44 — Aire acondicionado no enfría · MEDIA · 👤 ASIGNADA · ↩ 06/07
• INC-031 · Hab 204 — Pierde agua el termotanque · ALTA · 🔧 EN_PROCESO
──────────────
🔧 INCIDENCIAS (4)
1. Hab 204 — Pierde agua el termotanque · ALTA · 🔧 EN_PROCESO
2. Hab 110 — Se quemó la lámpara del velador · BAJA · ✅ CERRADA
💡 NOTAS DE HUÉSPED (2)
5. Hab 110 — Pidió almohada extra para la 110
👁 NOVEDADES (1)
7. Recepción — Llega el técnico del ascensor mañana 9hs
──────────────
Cerrado 15:45 · /reporte REP-012
```

Cambios respecto de la plantilla actual: los pendientes van **arriba**, con su ID accionable y una
marca `↩ dd/mm` si vienen arrastrados de otro día; las descripciones se truncan a 60 caracteres.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_report_template.py`:

```python
import report_processor


def _item(**kw):
    base = {"id": 1, "timestamp": "2026-08-09T10:00:00", "tipo": "INCIDENCIA",
            "estado": "NUEVA", "ubicacion": "Habitación 204", "descripcion": "Pierde agua",
            "prioridad": "ALTA"}
    base.update(kw)
    return base


def _render(items, carryover=()):
    return report_processor.render_shift_report(
        items, display_id="REP-012", employee_name="Jaime A",
        department="MANTENIMIENTO", carryover=carryover)


def test_pendientes_go_before_the_detail():
    """Lo que falta se lee primero; es la razón de ser del informe."""
    texto = _render([_item(descripcion="abierta")])
    assert texto.index("QUEDA PENDIENTE") < texto.index("INCIDENCIAS (1)")


def test_pendiente_line_carries_actionable_id():
    texto = _render([_item(id=18, descripcion="abierta")])
    assert "INC-018" in texto


def test_carryover_is_marked_with_its_date():
    viejo = _item(id=18, timestamp="2026-07-02T10:00:00", descripcion="cerradura")
    texto = _render([], carryover=[viejo])
    assert "↩ 02/07" in texto
    assert "QUEDA PENDIENTE (1)" in texto


def test_items_of_the_day_are_not_marked_as_carryover():
    texto = _render([_item(descripcion="de hoy")])
    assert "↩" not in texto


def test_closed_items_are_not_pendientes():
    texto = _render([_item(estado="CERRADA"), _item(estado="CANCELADA")])
    assert "QUEDA PENDIENTE" not in texto


def test_long_descriptions_are_truncated():
    largo = "x" * 200
    texto = _render([_item(descripcion=largo)])
    assert "x" * 200 not in texto
    assert "…" in texto


def test_room_labels_are_shortened():
    texto = _render([_item(ubicacion="Habitación 204")])
    assert "Hab 204" in texto
    assert "Habitación 204" not in texto


def test_no_pendientes_section_when_everything_is_closed():
    texto = _render([_item(estado="CERRADA")])
    assert "QUEDA PENDIENTE" not in texto
    assert "INCIDENCIAS (1)" in texto
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `venv/bin/pytest tests/test_report_template.py -v`
Esperado: FAIL — `render_shift_report() got an unexpected keyword argument 'carryover'`.

- [ ] **Step 3: Implementar**

En `report_processor.py`, agregar cerca de los helpers de arriba:

```python
_MAX_DESC = 60


def _truncate(texto: str, limite: int = _MAX_DESC) -> str:
    """Colapsa espacios y corta. Un informe de 15 ítems sin esto no se lee en el celular."""
    texto = " ".join(texto.split())
    return texto if len(texto) <= limite else texto[:limite - 1].rstrip() + "…"


def _pendiente_line(item: dict, *, day: str | None) -> str:
    """Línea de pendiente, con ID accionable y marca de arrastre si viene de otro día."""
    estado = item.get("estado") or IncidentState.NUEVA
    ubic = shorten_room_label(_value(item, "ubicacion")) or "Sin ubicación"
    desc = _truncate(_value(item, "descripcion") or "Sin descripción")
    prio = _value(item, "prioridad")
    prio_part = f" · {prio}" if prio else ""
    did = storage.generate_display_id(ReportType.INCIDENCIA, item.get("id", 0))
    marca = ""
    ts = _value(item, "timestamp")
    if day and ts and ts[:10] != day:
        try:
            marca = f" · ↩ {datetime.fromisoformat(ts).strftime('%d/%m')}"
        except ValueError:
            marca = " · ↩"
    return (f"• {did} · {ubic} — {desc}{prio_part} · "
            f"{ESTADO_EMOJI.get(estado, '')} {estado}{marca}")
```

Importar arriba del archivo: `from presenters.format_location import shorten_room_label`.

Reemplazar el cuerpo de `render_shift_report` por:

```python
def render_shift_report(items: list[dict], *, display_id: str, employee_name: str,
                        department: str | None, carryover: list[dict] | tuple = (),
                        closed_at: str | None = None) -> str:
    """Plantilla única del informe. `carryover` son incidencias abiertas de días
    anteriores: se muestran entre los pendientes pero no cuentan como ítems del día."""
    total = len(items)
    day = items[0].get("timestamp", "")[:10] if items else None

    rng = _time_range(items)
    meta = f"{rng} · " if rng else ""
    header2 = f"👤 {employee_name}" + (f" · {department}" if department else "")
    lines = [
        f"📋 INFORME DE TURNO — {display_id}",
        header2,
        f"🕐 {meta}{total} ítem{'s' if total != 1 else ''}",
    ]

    section_lines, pendientes_hoy = _render_item_sections(items)
    pendientes = list(carryover) + pendientes_hoy
    if pendientes:
        lines.append("")
        lines.append(f"⚠️ QUEDA PENDIENTE ({len(pendientes)})")
        for it in pendientes:
            lines.append(_pendiente_line(it, day=day))

    lines.append(_DIVIDER)
    lines.extend(section_lines or ["Sin ítems cargados hoy."])
    lines.append(_DIVIDER)

    if closed_at:
        try:
            ct = datetime.fromisoformat(closed_at).strftime("%H:%M")
            lines.append(f"Cerrado {ct} · /reporte {display_id}")
        except ValueError:
            lines.append(f"/reporte {display_id}")
    return "\n".join(lines)
```

En `_incident_line`, `_guest_line` y `_observation_line`, envolver la descripción con `_truncate(...)`
y la ubicación con `shorten_room_label(...)`, para que el detalle se corte igual que los pendientes.

> La sección `⏳ QUEDA PENDIENTE PARA EL PRÓXIMO TURNO` del final desaparece: ahora está arriba.
> `render_sector_rollup` sigue usando `_render_item_sections`, así que hereda el truncado sin cambios.

- [ ] **Step 4: Correr y verificar que pasan**

Run: `venv/bin/pytest tests/test_report_template.py -v`
Esperado: PASS los ocho.

- [ ] **Step 5: Correr la suite entera — acá es donde algo se rompe**

Run: `venv/bin/pytest -q`
Esperado: verde. Si `tests/test_hotel_scenarios.py` falla porque busca el texto viejo
(`"QUEDA PENDIENTE PARA EL PRÓXIMO TURNO"` o `"🎯 Handover"`), actualizá esa aserción al texto
nuevo — el cambio de plantilla es intencional, no un bug.

- [ ] **Step 6: Commit**

```bash
git add report_processor.py tests/test_report_template.py tests/test_hotel_scenarios.py
git commit -m "feat(reportes): plantilla con pendientes arriba, IDs accionables y truncado

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 5: `/reporte` usa el día

**Files:**
- Modify: `handlers/command_handler.py:253` (`_DEFAULT_HOURS`), `:294-307` (rama `Nh`), `:342-354`
- Test: `tests/test_hotel_scenarios.py`

**Interfaces:**
- Consumes: `storage.get_classifications_for_employee_day`, `storage.get_open_incidents_before_day` (Task 2);
  `report_processor.render_shift_report(..., carryover=...)` (Task 4).
- Produces: `context.user_data["pending_report_items"]` pasa a tener la forma
  `{"items": [...], "carryover": [...], "day": "YYYY-MM-DD"}`. La clave `hours` desaparece.

> **Ojo:** `handlers/_corrections.py:48` y `:93` también escriben `pending_report_items` con `hours`.
> Como el botón de corregir se elimina en la Task 6, esos dos writes quedan muertos; se limpian ahí.

- [ ] **Step 1: Escribir el test que falla**

Agregar a `tests/test_hotel_scenarios.py`. Los helpers ya existen en el archivo: `make_context()`,
`make_message_update(user_id, text)`, `seed_classification(employee, result, message)`,
`latest_reply_text(update)`, la fixture autouse `isolated_db`, y las constantes `EMP_MANT`
(telegram_id 203) e `INCIDENCIA_204`.

```python
@pytest.mark.asyncio
async def test_reporte_trae_el_dia_aunque_ya_este_consolidado():
    """El bug original: consolidar una vez hacía desaparecer los ítems para siempre."""
    from handlers.command_handler import handle_reporte

    primero = seed_classification(EMP_MANT, INCIDENCIA_204, "pierde agua la 204")
    segundo = seed_classification(EMP_MANT, INCIDENCIA_204, "otra cosa en la 204")
    # el primero ya fue consolidado en un informe anterior
    storage.link_classifications_to_report([primero], 99)

    update = make_message_update(EMP_MANT["telegram_id"])
    context = make_context()
    await handle_reporte(update, context)

    texto = latest_reply_text(update)
    assert "No reportaste nada" not in texto
    assert "INFORME DE TURNO" in texto
    ids = [i["id"] for i in context.user_data["pending_report_items"]["items"]]
    assert sorted(ids) == sorted([primero, segundo]), "el ya consolidado tiene que seguir apareciendo"
```

> `seed_classification` usa `storage.save`, que sella el `timestamp` con `datetime.now()` — o sea
> hoy. Por eso el test no necesita fabricar fechas.

- [ ] **Step 2: Correr y verificar que falla**

Run: `venv/bin/pytest tests/test_hotel_scenarios.py -k consolidado -v`
Esperado: FAIL — devuelve "No reportaste nada en las últimas 12h".

- [ ] **Step 3: Implementar**

En `handlers/command_handler.py`:

1. Borrar `_DEFAULT_HOURS = 12` (línea 253).
2. Borrar el bloque completo de `/reporte Nh` (líneas 294-307).
3. Reemplazar el bloque final (líneas 342-354) por:

```python
    # /reporte sin args → la tira del día
    hoy = date.today().isoformat()
    items = storage.get_classifications_for_employee_day(tid, hoy)
    carryover = storage.get_open_incidents_before_day(tid, hoy)

    if not items and not carryover:
        await update.message.reply_text(
            "Hoy no cargaste nada todavía. Mandame lo que haya pasado y después poné /reporte."
        )
        return

    context.user_data["pending_report_items"] = {
        "items": items, "carryover": carryover, "day": hoy,
    }
    text, keyboard = report_processor.format_report_summary(items, user, carryover)
    await update.message.reply_text(text, reply_markup=keyboard)
```

4. Agregar `from datetime import date` a los imports.
5. En el mensaje de error de args inválidos (línea 314), sacar la mención a `/reporte 6h`:
   `"Usá /reporte o /reporte REP-N."`

En `report_processor.py`, cambiar la firma de `format_report_summary`:

```python
def format_report_summary(items: list[dict], employee: dict,
                          carryover: list[dict] | tuple = ()) -> tuple[str, InlineKeyboardMarkup]:
    """Borrador previo a confirmar, con la plantilla del informe."""
    text = render_shift_report(
        items, display_id="(borrador)",
        employee_name=employee.get("nombre", ""),
        department=employee.get("departamento"),
        carryover=carryover,
    )
    text += "\n\n¿Sumás algo más o lo cerramos?"
    return text, _REPORT_DRAFT_KEYBOARD
```

(`_REPORT_DRAFT_KEYBOARD` se define en la Task 6; por ahora dejá `_CONFIRM_KEYBOARD` y cambialo ahí.)

- [ ] **Step 4: Correr y verificar que pasa**

Run: `venv/bin/pytest tests/test_hotel_scenarios.py -k consolidado -v`
Esperado: PASS.

- [ ] **Step 5: Correr la suite entera**

Run: `venv/bin/pytest -q`
Esperado: verde. Los tests que ejercitaban `/reporte 6h` van a fallar — borralos, la funcionalidad
se eliminó a propósito.

- [ ] **Step 6: Commit**

```bash
git add handlers/command_handler.py report_processor.py tests/
git commit -m "feat(reportes): /reporte devuelve el día calendario y elimina la ventana Nh

La ventana de 12h dejaba afuera todo lo de sesiones anteriores y el filtro
report_id IS NULL hacía que un ítem consolidado no volviera a aparecer nunca:
16 de 39 clasificaciones no entraron jamás en un informe.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 6: Botón "Sumar algo" y cierre con upsert

**Files:**
- Modify: `presenters/keyboards.py`, `presenters/__init__.py`
- Modify: `report_processor.py` (`_CONFIRM_KEYBOARD` → `_REPORT_DRAFT_KEYBOARD`)
- Modify: `handlers/callback_handler.py:219-245` (`_handle_report_confirm`), `:248-265`, `:284-290`, `:296-317`
- Modify: `handlers/_corrections.py:48,93` (limpiar los writes muertos)
- Test: `tests/test_hotel_scenarios.py`

**Interfaces:**
- Consumes: `storage.upsert_report_for_day` (Task 3).
- Produces: `context.user_data["report_draft_open"]: bool` — bandera que hace que, al confirmar un
  ítem nuevo, el bot vuelva a mostrar el borrador solo.

**Cómo funciona "sumar algo", en una línea:** no hace falta ninguna máquina de estados nueva.
El ítem se carga por el flujo normal y, como la ventana es "hoy sin filtro de report_id",
aparece solo en el informe. La bandera existe solo para volver a mostrarte el borrador sin que
tengas que tipear `/reporte` de nuevo.

- [ ] **Step 1: Escribir los tests que fallan**

`make_callback_update(user_id, data)` (línea 125) devuelve un `update` con `.callback_query` ya
armado, así que se le pasa directo a `handle_callback`. `make_context()` ya deja `ctx.args = []`
y `ctx.bot.send_message` como `AsyncMock`.

```python
@pytest.mark.asyncio
async def test_sumar_algo_reabre_el_borrador_solo():
    """Tras confirmar un ítem con el borrador abierto, el informe vuelve sin tipear /reporte."""
    from handlers.callback_handler import handle_callback

    context = make_context({
        "report_draft_open": True,
        "pending": {"result": dict(INCIDENCIA_204), "original_text": "pierde agua"},
    })
    update = make_callback_update(EMP_MANT["telegram_id"], "confirm")
    await handle_callback(update, context)

    enviados = [c.kwargs.get("text", "") for c in context.bot.send_message.call_args_list]
    assert any("INFORME DE TURNO" in t for t in enviados)


@pytest.mark.asyncio
async def test_cerrar_dos_veces_el_mismo_dia_no_crea_dos_reps():
    from handlers.command_handler import handle_reporte
    from handlers.callback_handler import handle_callback

    seed_classification(EMP_MANT, INCIDENCIA_204, "pierde agua la 204")

    for _ in range(2):
        update = make_message_update(EMP_MANT["telegram_id"])
        context = make_context()
        await handle_reporte(update, context)
        cierre = make_callback_update(EMP_MANT["telegram_id"], "report_confirm_all")
        await handle_callback(cierre, context)

    with storage._conn() as con:
        assert con.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 1
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `venv/bin/pytest tests/test_hotel_scenarios.py -k "sumar_algo or dos_veces" -v`
Esperado: FAIL.

- [ ] **Step 3: Implementar**

En `presenters/keyboards.py`:

```python
REPORT_DRAFT_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("✅ Listo, cerrar", callback_data="report_confirm_all"),
        InlineKeyboardButton("➕ Sumar algo", callback_data="report_add_item"),
    ]
])
```

Exportarlo en `presenters/__init__.py`. En `report_processor.py`, borrar `_CONFIRM_KEYBOARD`
e importar `REPORT_DRAFT_KEYBOARD` como `_REPORT_DRAFT_KEYBOARD`.

En `handlers/callback_handler.py`:

1. En `_handle_report_confirm`, cambiar `storage.create_report(employee)` por:

```python
    day = pending.get("day") or date.today().isoformat()
    report_id = storage.upsert_report_for_day(employee, day)
    classification_ids = [i["id"] for i in items]
    storage.link_classifications_to_report(classification_ids, report_id)
    context.user_data.pop("pending_report_items", None)
    context.user_data.pop("report_draft_open", None)
```

(el arrastre **no** se linkea: `items` no lo incluye).

2. Reemplazar `_handle_report_correct_start` por:

```python
async def _handle_report_add_item(query, context) -> None:
    """No abre ninguna máquina de estados: el ítem entra por el flujo normal y, como la
    ventana del informe es el día entero, aparece solo. La bandera es solo para volver
    a mostrar el borrador sin tipear /reporte otra vez."""
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    context.user_data["report_draft_open"] = True
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Dale, mandame qué querés sumar (texto, audio o foto).",
    )
```

3. En `handle_callback`, cambiar el ruteo:

```python
    if action == "report_add_item":
        await _handle_report_add_item(query, context)
        return
```

y borrar la rama `if action == "report_correct":`.

4. En la rama `if action == "confirm":`, después de guardar el ítem y mandar
   `"✅ Guardado. Gracias, {nombre}."`, agregar:

```python
        if context.user_data.get("report_draft_open"):
            hoy = date.today().isoformat()
            tid = query.from_user.id
            items = storage.get_classifications_for_employee_day(tid, hoy)
            carryover = storage.get_open_incidents_before_day(tid, hoy)
            context.user_data["pending_report_items"] = {
                "items": items, "carryover": carryover, "day": hoy}
            texto, teclado = report_processor.format_report_summary(items, employee, carryover)
            await context.bot.send_message(
                chat_id=query.message.chat_id, text=texto, reply_markup=teclado)
```

5. Agregar `from datetime import date` a los imports.

En `handlers/_corrections.py`, borrar los dos writes de `pending_report_items` (líneas 48 y 93) y
lo que quede huérfano de la corrección de ítems del informe. **No toques** la corrección de un ítem
al cargarlo — ese flujo sigue vivo.

- [ ] **Step 4: Correr y verificar que pasan**

Run: `venv/bin/pytest -q`
Esperado: verde.

- [ ] **Step 5: Commit**

```bash
git add presenters/ handlers/ report_processor.py tests/
git commit -m "feat(reportes): botón 'Sumar algo' y cierre idempotente del informe del día

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 7: Pendientes en Sheets

**Files:**
- Modify: `sheets_sync.py:24-35` (`_HEADERS`), `:165-183` (`_sync_reporte_sync`)
- Test: `tests/test_sheets_sync.py`

**Interfaces:**
- Consumes: `report_processor.format_report_for_sheet`, `storage.generate_display_id`.
- Produces: la hoja `Reportes de turno` pasa de 6 a 8 columnas (rango `A:H`), y la fila se
  actualiza por ID en vez de appendearse siempre.

**Por qué las columnas van al final:** la hoja ya tiene datos. Insertar en el medio correría los
valores existentes una columna y desalinearía todo el histórico.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `tests/test_sheets_sync.py`, con el helper `_make_ws_mock(col_a_values)` y el
`patch.object(sheets_sync, "_get_worksheet", ...)` que ya usa el archivo (ver
`test_sync_incidencia_uses_filter_friendly_room_location:162`). El ws es un `MagicMock`,
así que la fila escrita se lee de `ws.append_row.call_args` o `ws.update.call_args`.

```python
REPORT_STUB = {"employee_name": "Jaime A", "closed_at": "2026-08-09T15:45:00"}


def test_reporte_row_has_pendientes_columns():
    items = [
        {"id": 18, "tipo": "INCIDENCIA", "estado": "NUEVA",
         "descripcion": "abierta", "ubicacion": "Hab 203"},
        {"id": 19, "tipo": "INCIDENCIA", "estado": "CERRADA",
         "descripcion": "cerrada", "ubicacion": "Hab 204"},
    ]
    ws = _make_ws_mock(col_a_values=["ID"])
    with patch.object(sheets_sync, "_get_worksheet", return_value=ws):
        sheets_sync._sync_reporte_sync(REPORT_STUB, items, "REP-012")

    fila = ws.append_row.call_args.args[0]
    assert len(fila) == 8, "la hoja pasó de 6 a 8 columnas"
    assert fila[6] == 1, "una sola pendiente"
    assert "INC-018" in fila[7]
    assert "INC-019" not in fila[7], "la cerrada no es pendiente"


def test_reporte_row_is_upserted_not_duplicated():
    """Cerrar dos veces el mismo día actualiza la fila; si no, la hoja se llena de duplicados."""
    ws = _make_ws_mock(col_a_values=["ID", "REP-012"])
    with patch.object(sheets_sync, "_get_worksheet", return_value=ws):
        sheets_sync._sync_reporte_sync(REPORT_STUB, [], "REP-012")

    ws.append_row.assert_not_called()
    ws.update.assert_called_once()
    rango = ws.update.call_args.args[0]
    assert rango == "A2:H2"
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `venv/bin/pytest tests/test_sheets_sync.py -k reporte -v`
Esperado: FAIL — `IndexError` (la fila tiene 6 columnas) y duplicado en el segundo test.

- [ ] **Step 3: Implementar**

En `sheets_sync.py`, extender el header:

```python
    "Reportes de turno": ["ID", "Fecha/hora de cierre", "Empleado",
                          "Cantidad de ítems", "Desglose", "Resumen / link",
                          "Pendientes", "IDs pendientes"],
```

Y reemplazar el final de `_sync_reporte_sync`:

```python
    pendientes = [i for i in items
                  if i.get("tipo") == ReportType.INCIDENCIA
                  and (i.get("estado") or IncidentState.NUEVA)
                  not in (IncidentState.CERRADA, IncidentState.CANCELADA)]
    ids_pendientes = ", ".join(
        generate_display_id(ReportType.INCIDENCIA, i["id"]) for i in pendientes)

    row = [
        display_id,
        report.get("closed_at") or report.get("started_at", ""),
        report.get("employee_name", ""),
        len(items),
        desglose,
        report_processor.format_report_for_sheet(items),
        len(pendientes),
        ids_pendientes,
    ]

    col_a = ws.col_values(1)
    if display_id in col_a:
        row_num = col_a.index(display_id) + 1
        ws.update(f"A{row_num}:H{row_num}", [row])
    else:
        ws.append_row(row)
```

Importar `generate_display_id` desde `storage` y `IncidentState` desde `config.enums` si no están.

- [ ] **Step 4: Correr y verificar que pasan**

Run: `venv/bin/pytest tests/test_sheets_sync.py -v`
Esperado: PASS.

- [ ] **Step 5: Commit**

```bash
git add sheets_sync.py tests/test_sheets_sync.py
git commit -m "feat(sheets): columnas de pendientes en Reportes de turno y upsert por ID

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 8: E2E del flujo completo

**Files:**
- Modify: `tests/test_hotel_scenarios.py`

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: nada nuevo; blinda el recorrido entero.

- [ ] **Step 1: Escribir el escenario**

```python
@pytest.mark.asyncio
async def test_escenario_dia_completo():
    """Cargo dos cosas, cierro el informe, y al día siguiente la que quedó abierta arrastra."""
    import report_processor
    from handlers.command_handler import handle_reporte
    from handlers.callback_handler import handle_callback

    abierta = seed_classification(EMP_MANT, INCIDENCIA_204, "pierde agua la 204")
    cerrada = seed_classification(EMP_MANT, INCIDENCIA_204, "lámpara quemada la 110")
    with storage._conn() as con:
        con.execute("UPDATE classifications SET estado='CERRADA' WHERE id=?", (cerrada,))

    # 1. /reporte muestra los dos ítems y una sola pendiente
    update = make_message_update(EMP_MANT["telegram_id"])
    context = make_context()
    await handle_reporte(update, context)
    borrador = latest_reply_text(update)
    assert "QUEDA PENDIENTE (1)" in borrador
    assert borrador.index("QUEDA PENDIENTE") < borrador.index("INCIDENCIAS")

    # 2. cerrar crea un REP y linkea los ítems del día (no el arrastre)
    await handle_callback(make_callback_update(EMP_MANT["telegram_id"], "report_confirm_all"), context)
    with storage._conn() as con:
        assert con.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 1
        linkeados = con.execute(
            "SELECT COUNT(*) FROM classifications WHERE report_id IS NOT NULL").fetchone()[0]
    assert linkeados == 2

    # 3. volver a pedirlo el mismo día no crea un segundo REP
    update2 = make_message_update(EMP_MANT["telegram_id"])
    context2 = make_context()
    await handle_reporte(update2, context2)
    await handle_callback(make_callback_update(EMP_MANT["telegram_id"], "report_confirm_all"), context2)
    with storage._conn() as con:
        assert con.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 1

    # 4. al día siguiente, la que sigue abierta aparece como arrastre marcada con ↩
    with storage._conn() as con:
        con.execute("UPDATE classifications SET timestamp = '2026-01-02T10:00:00' WHERE id=?",
                    (abierta,))
    arrastre = storage.get_open_incidents_before_day(EMP_MANT["telegram_id"], "2026-01-03")
    assert [i["id"] for i in arrastre] == [abierta]
    texto = report_processor.render_shift_report(
        [], display_id="REP-002", employee_name=EMP_MANT["nombre"],
        department=EMP_MANT["departamento"], carryover=arrastre)
    assert "↩ 02/01" in texto
```

- [ ] **Step 2: Correr la suite completa**

Run: `venv/bin/pytest -q`
Esperado: verde, con más tests que los 232 de partida.

- [ ] **Step 3: Verificación manual contra la base real**

```bash
venv/bin/python -c "
import sqlite3
from datetime import date
c = sqlite3.connect('data/hotel_bot.db')
hoy = date.today().isoformat()
for nombre, tid in (('Jaime', 7391337590), ('Juan', 8709342265)):
    arrastre = c.execute(
        \"SELECT COUNT(*) FROM classifications WHERE employee_telegram_id=?\"
        \" AND date(timestamp)<? AND tipo='INCIDENCIA'\"
        \" AND COALESCE(estado,'NUEVA') NOT IN ('CERRADA','CANCELADA')\",
        (tid, hoy)).fetchone()[0]
    print(f'{nombre}: arrastre abierto = {arrastre}')
"
```

Esperado exacto: **Jaime 2** (incidencias #20 y #21) y **Juan 1** (#18). Las tres son huérfanas
hoy inalcanzables; que reaparezcan es la prueba de que el bug quedó cerrado.

> #18 tiene `employee_telegram_id` en NULL en la base actual: es de Juan, y solo aparece si el
> backfill de la Task 1 corrió. Si Juan da 0, la migración v2 no se aplicó.

- [ ] **Step 4: Prueba a mano en Telegram**

Levantar el bot, mandar `/reporte` como Jaime y verificar:
1. Aparece la tira del día (no "no reportaste nada").
2. Salen 2 incidencias viejas bajo `⚠️ QUEDA PENDIENTE` con su `↩ dd/mm` (#20 del 06/07 y #21 del
   06/07). Como Juan, tiene que salir 1 (#18 del 02/07).
3. "➕ Sumar algo" deja cargar un ítem y el borrador vuelve solo.
4. "✅ Listo, cerrar" crea el REP y le llega a Juan.
5. `/reporte` de nuevo: mismo REP-N, no uno nuevo.
6. En Sheets, la fila del REP tiene las columnas `Pendientes` e `IDs pendientes` cargadas.

- [ ] **Step 5: Commit**

```bash
git add tests/test_hotel_scenarios.py
git commit -m "test(reportes): escenario E2E del día completo con arrastre

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Al terminar

Actualizar `tasks/todo.md`:
- Sprint C.1 a la tabla de completados.
- Sacar de pendientes: "migrar consolidación de reportes a telegram_id" (lo hace la Task 1).
- Anotar en `tasks/lessons.md`: la ventana deslizante de N horas combinada con un filtro de
  "ya consolidado" pierde datos en silencio cuando el uso es esporádico. El síntoma que se ve es
  "no hay nada que reportar"; la causa está dos capas más abajo, en el WHERE.
