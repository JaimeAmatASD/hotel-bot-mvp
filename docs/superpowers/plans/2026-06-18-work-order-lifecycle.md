# Work-Order Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir el ciclo de vida de incidencias en un work-order de 6 estados (NUEVA → ASIGNADA → EN_PROCESO → RESUELTA → CERRADA + CANCELADA) con delegación a personas concretas, validación de cierre en dos pasos, y trazabilidad de quién asignó/resolvió/validó.

**Architecture:** Se respeta la arquitectura por capas existente. La transición de estado sigue centralizada en `storage/events.update_incident_state_atomic` (único punto, `BEGIN IMMEDIATE`). Los permisos se amplían en `permissions.py` con una distinción acción-de-gestión vs acción-de-ejecución. El teclado y los flujos de selección de persona viven en `notifier/format.py` + `handlers/callback_handler.py`, siempre con callbacks de 3 partes.

**Tech Stack:** Python 3.11 (StrEnum), SQLite (`sqlite3`), python-telegram-bot v20, gspread, pytest + unittest.

**Spec de referencia:** `docs/superpowers/specs/2026-06-17-work-order-lifecycle-design.md`

---

## File Structure

| Archivo | Responsabilidad | Cambio |
|---------|-----------------|--------|
| `config/enums.py` | enum `IncidentState` | añadir NUEVA/RESUELTA/CANCELADA, quitar ABIERTA |
| `config/transitions.py` (**nuevo**) | tabla de transiciones válidas (acción→estado, estados origen) — única fuente de verdad de la máquina de estados | crear |
| `storage/schema.py` | columnas de trazabilidad + default NUEVA | modificar |
| `storage/migrations.py` | migración de datos ABIERTA→NUEVA | modificar |
| `storage/events.py` | `update_incident_state_atomic` con acción explícita + trazabilidad | modificar |
| `permissions.py` | `can_do_action`, `assignable_targets`, `assignable_departments` | modificar |
| `notifier/format.py` | teclados por estado + picker de persona/depto | modificar |
| `notifier/state_change.py` | notificar al asignado y a los managers | modificar |
| `notifier/__init__.py` | exportar funciones nuevas | modificar |
| `handlers/callback_handler.py` | routing de acciones + asignar/reasignar/assign_to/assign_dept | modificar |
| `presenters/constants.py` | emojis/labels de acciones y estados nuevos | modificar |
| `presenters/format_incidents.py`, `format_history.py` | mostrar estados/acciones nuevos | modificar |
| `sheets_sync.py` | columnas Asignado por / Resuelto por / Validado por | modificar |
| `tests/...` | unit + e2e | crear/modificar |

**Vocabulario de acciones (verbos de callback), fijo para todo el plan:**
`tomar`, `asignar`, `reasignar`, `comenzar`, `terminado`, `validar`, `reabrir`, `cancelar`.
Más dos callbacks de selección: `assign_to:{id}:{telegram_id}` y `assign_dept:{id}:{DEPTO}`.

---

## Task 1: Estados nuevos + máquina de transiciones

**Files:**
- Modify: `config/enums.py:5-9`
- Create: `config/transitions.py`
- Test: `tests/test_transitions.py`

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_transitions.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.enums import IncidentState
from config.transitions import ACTION_TO_STATE, EXPECTED_FROM, action_target_state


def test_estados_existen():
    assert IncidentState.NUEVA == "NUEVA"
    assert IncidentState.RESUELTA == "RESUELTA"
    assert IncidentState.CANCELADA == "CANCELADA"
    assert not hasattr(IncidentState, "ABIERTA")


def test_action_to_state_cubre_todas_las_acciones():
    assert ACTION_TO_STATE["tomar"] == IncidentState.ASIGNADA
    assert ACTION_TO_STATE["asignar"] == IncidentState.ASIGNADA
    assert ACTION_TO_STATE["reasignar"] == IncidentState.ASIGNADA
    assert ACTION_TO_STATE["reabrir"] == IncidentState.ASIGNADA
    assert ACTION_TO_STATE["comenzar"] == IncidentState.EN_PROCESO
    assert ACTION_TO_STATE["terminado"] == IncidentState.RESUELTA
    assert ACTION_TO_STATE["validar"] == IncidentState.CERRADA
    assert ACTION_TO_STATE["cancelar"] == IncidentState.CANCELADA


def test_expected_from_correctos():
    assert EXPECTED_FROM["comenzar"] == [IncidentState.ASIGNADA]
    assert EXPECTED_FROM["terminado"] == [IncidentState.EN_PROCESO]
    assert EXPECTED_FROM["validar"] == [IncidentState.RESUELTA]
    assert EXPECTED_FROM["reabrir"] == [IncidentState.RESUELTA]
    assert IncidentState.NUEVA in EXPECTED_FROM["cancelar"]
    assert IncidentState.RESUELTA in EXPECTED_FROM["cancelar"]
    assert IncidentState.CERRADA not in EXPECTED_FROM["cancelar"]


def test_action_target_state_helper():
    assert action_target_state("validar") == IncidentState.CERRADA
    assert action_target_state("desconocida") is None
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `venv/bin/pytest tests/test_transitions.py -q`
Expected: FAIL (`ImportError: cannot import name ... config.transitions`).

- [ ] **Step 3: Modificar el enum**

En `config/enums.py` reemplazar la clase `IncidentState` (líneas 5-9) por:

```python
class IncidentState(StrEnum):
    NUEVA = "NUEVA"
    ASIGNADA = "ASIGNADA"
    EN_PROCESO = "EN_PROCESO"
    RESUELTA = "RESUELTA"
    CERRADA = "CERRADA"
    CANCELADA = "CANCELADA"
```

- [ ] **Step 4: Crear `config/transitions.py`**

```python
"""Máquina de estados de incidencias: única fuente de verdad de transiciones.

Cada acción (verbo del callback) mapea a un estado destino y a la lista de
estados de origen permitidos. `asignar`/`reasignar` abren el selector de persona;
la transición real ocurre vía la acción `assign_to` (ver callback_handler)."""
from config.enums import IncidentState

# Estado destino de cada acción
ACTION_TO_STATE = {
    "tomar":     IncidentState.ASIGNADA,
    "asignar":   IncidentState.ASIGNADA,
    "reasignar": IncidentState.ASIGNADA,
    "reabrir":   IncidentState.ASIGNADA,
    "comenzar":  IncidentState.EN_PROCESO,
    "terminado": IncidentState.RESUELTA,
    "validar":   IncidentState.CERRADA,
    "cancelar":  IncidentState.CANCELADA,
}

# Estados de origen válidos por acción
EXPECTED_FROM = {
    "tomar":     [IncidentState.NUEVA],
    "asignar":   [IncidentState.NUEVA, IncidentState.ASIGNADA, IncidentState.EN_PROCESO],
    "reasignar": [IncidentState.ASIGNADA, IncidentState.EN_PROCESO],
    "reabrir":   [IncidentState.RESUELTA],
    "comenzar":  [IncidentState.ASIGNADA],
    "terminado": [IncidentState.EN_PROCESO],
    "validar":   [IncidentState.RESUELTA],
    "cancelar":  [IncidentState.NUEVA, IncidentState.ASIGNADA,
                  IncidentState.EN_PROCESO, IncidentState.RESUELTA],
}

# Acciones que requieren rol manager (gestión) vs. ejecutor
MANAGEMENT_ACTIONS = {"asignar", "tomar", "reasignar", "validar", "reabrir", "cancelar"}
EXECUTION_ACTIONS = {"comenzar", "terminado"}

# Estados terminales (sin botones)
TERMINAL_STATES = {IncidentState.CERRADA, IncidentState.CANCELADA}


def action_target_state(action: str):
    """Estado destino de una acción, o None si la acción es desconocida."""
    return ACTION_TO_STATE.get(action)
```

- [ ] **Step 5: Correr el test y verificar que pasa**

Run: `venv/bin/pytest tests/test_transitions.py -q`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add config/enums.py config/transitions.py tests/test_transitions.py
git commit -m "feat(enums): estados work-order + tabla de transiciones"
```

---

## Task 2: Migración de datos + columnas de trazabilidad

**Files:**
- Modify: `storage/schema.py:100-110` (loop de columnas)
- Modify: `storage/migrations.py:17`
- Test: `tests/test_migrations.py`

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_migrations.py
import sys, tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parent.parent))

import storage
from storage.migrations import apply_pending


def _cols(con, table):
    return [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]


def test_columnas_trazabilidad_existen():
    with tempfile.TemporaryDirectory() as d:
        with patch.object(storage, "DB_PATH", Path(d) / "t.db"):
            storage.init_db()
            with storage._conn() as con:
                cols = _cols(con, "classifications")
    for c in ("assigned_by", "resolved_by", "resolved_at", "closed_by",
              "cancelled_by", "cancel_reason"):
        assert c in cols, f"falta columna {c}"


def test_default_estado_es_nueva():
    with tempfile.TemporaryDirectory() as d:
        with patch.object(storage, "DB_PATH", Path(d) / "t.db"):
            storage.init_db()
            with storage._conn() as con:
                con.execute(
                    "INSERT INTO classifications (timestamp, employee_name, message) "
                    "VALUES ('2026-01-01','Ana','x')"
                )
                estado = con.execute(
                    "SELECT estado FROM classifications LIMIT 1"
                ).fetchone()[0]
    assert estado == "NUEVA"


def test_migracion_renombra_abierta_a_nueva():
    with tempfile.TemporaryDirectory() as d:
        with patch.object(storage, "DB_PATH", Path(d) / "t.db"):
            storage.init_db()
            with storage._conn() as con:
                con.execute(
                    "INSERT INTO classifications (timestamp, employee_name, message, estado) "
                    "VALUES ('2026-01-01','Ana','x','ABIERTA')"
                )
            apply_pending()
            with storage._conn() as con:
                estados = [r[0] for r in con.execute(
                    "SELECT estado FROM classifications").fetchall()]
    assert estados == ["NUEVA"]
    assert "ABIERTA" not in estados
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `venv/bin/pytest tests/test_migrations.py -q`
Expected: FAIL (columnas faltantes / estado default 'ABIERTA').

- [ ] **Step 3: Ampliar el loop de columnas en `storage/schema.py`**

Reemplazar el bloque de líneas 100-110 por:

```python
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
```

- [ ] **Step 4: Registrar la migración de datos en `storage/migrations.py`**

Reemplazar la línea 17 (`MIGRATIONS: list[Migration] = []`) por:

```python
def _rename_abierta_to_nueva(con) -> None:
    con.execute("UPDATE classifications SET estado='NUEVA' WHERE estado='ABIERTA'")


MIGRATIONS: list[Migration] = [
    (1, _rename_abierta_to_nueva),
]
```

- [ ] **Step 5: Correr el test y verificar que pasa**

Run: `venv/bin/pytest tests/test_migrations.py -q`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add storage/schema.py storage/migrations.py tests/test_migrations.py
git commit -m "feat(storage): columnas de trazabilidad + migración ABIERTA→NUEVA"
```

---

## Task 3: Transiciones atómicas con acción explícita y trazabilidad

**Files:**
- Modify: `storage/events.py:67-162` (`update_incident_state_atomic`)
- Modify: `storage/events.py:97` (default fallback)
- Test: `tests/test_incident_actions.py` (reescribir la clase `TestStorageTransitions`)

- [ ] **Step 1: Escribir/reemplazar los tests de transición**

Reemplazar **toda** la clase `TestStorageTransitions` (líneas 40-124 de `tests/test_incident_actions.py`) por:

```python
class TestStorageTransitions(unittest.TestCase):

    ENC = {"telegram_id": 444444444, "nombre": "Carlos Encargado Mant",
           "rol": "ENCARGADO", "departamento": "MANTENIMIENTO"}
    EMP = {"telegram_id": 222222222, "nombre": "Andrei Popescu",
           "rol": "EMPLEADO", "departamento": "MANTENIMIENTO"}

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db"
        self.patcher = patch.object(storage, "DB_PATH", self.db_path)
        self.patcher.start()
        storage.init_db()

    def tearDown(self):
        self.patcher.stop()

    def _seed(self, estado="NUEVA", categoria="MANTENIMIENTO"):
        with storage._conn() as con:
            return _seed_incident(con, categoria=categoria, estado=estado)

    def test_asignar_a_otra_persona(self):
        iid = self._seed("NUEVA")
        r = storage.update_incident_state_atomic(
            iid, "ASIGNADA", self.ENC, ["NUEVA"],
            action="asignar", assignee_telegram_id=222222222)
        self.assertTrue(r["success"])
        inc = storage.get_incident(iid)
        self.assertEqual(inc["estado"], "ASIGNADA")
        self.assertEqual(int(inc["assigned_to_telegram_id"]), 222222222)
        self.assertEqual(int(inc["assigned_by"]), 444444444)

    def test_tomar_para_si(self):
        iid = self._seed("NUEVA")
        storage.update_incident_state_atomic(
            iid, "ASIGNADA", self.ENC, ["NUEVA"], action="tomar")
        inc = storage.get_incident(iid)
        self.assertEqual(int(inc["assigned_to_telegram_id"]), 444444444)

    def test_comenzar_marca_en_proceso(self):
        iid = self._seed("ASIGNADA")
        r = storage.update_incident_state_atomic(
            iid, "EN_PROCESO", self.EMP, ["ASIGNADA"], action="comenzar")
        self.assertTrue(r["success"])
        self.assertEqual(storage.get_incident(iid)["estado"], "EN_PROCESO")

    def test_terminado_guarda_resolved_by(self):
        iid = self._seed("EN_PROCESO")
        r = storage.update_incident_state_atomic(
            iid, "RESUELTA", self.EMP, ["EN_PROCESO"], action="terminado")
        self.assertTrue(r["success"])
        inc = storage.get_incident(iid)
        self.assertEqual(inc["estado"], "RESUELTA")
        self.assertEqual(int(inc["resolved_by"]), 222222222)
        self.assertIsNotNone(inc["resolved_at"])

    def test_validar_cierra_con_closed_by(self):
        iid = self._seed("RESUELTA")
        r = storage.update_incident_state_atomic(
            iid, "CERRADA", self.ENC, ["RESUELTA"], action="validar")
        self.assertTrue(r["success"])
        inc = storage.get_incident(iid)
        self.assertEqual(inc["estado"], "CERRADA")
        self.assertEqual(int(inc["closed_by"]), 444444444)
        self.assertIsNotNone(inc["closed_at"])
        self.assertIsNotNone(inc["resolution_time_minutes"])

    def test_reabrir_vuelve_a_asignada_sin_borrar_assignee(self):
        iid = self._seed("NUEVA")
        storage.update_incident_state_atomic(
            iid, "ASIGNADA", self.ENC, ["NUEVA"],
            action="asignar", assignee_telegram_id=222222222)
        storage.update_incident_state_atomic(iid, "EN_PROCESO", self.EMP, ["ASIGNADA"], action="comenzar")
        storage.update_incident_state_atomic(iid, "RESUELTA", self.EMP, ["EN_PROCESO"], action="terminado")
        r = storage.update_incident_state_atomic(
            iid, "ASIGNADA", self.ENC, ["RESUELTA"], action="reabrir")
        self.assertTrue(r["success"])
        inc = storage.get_incident(iid)
        self.assertEqual(inc["estado"], "ASIGNADA")
        self.assertEqual(int(inc["assigned_to_telegram_id"]), 222222222)

    def test_cancelar_guarda_motivo(self):
        iid = self._seed("ASIGNADA")
        r = storage.update_incident_state_atomic(
            iid, "CANCELADA", self.ENC, ["NUEVA", "ASIGNADA", "EN_PROCESO", "RESUELTA"],
            action="cancelar", cancel_reason="duplicada")
        self.assertTrue(r["success"])
        inc = storage.get_incident(iid)
        self.assertEqual(inc["estado"], "CANCELADA")
        self.assertEqual(int(inc["cancelled_by"]), 444444444)
        self.assertEqual(inc["cancel_reason"], "duplicada")

    def test_transicion_invalida_rechazada(self):
        iid = self._seed("NUEVA")
        r = storage.update_incident_state_atomic(
            iid, "RESUELTA", self.EMP, ["EN_PROCESO"], action="terminado")
        self.assertFalse(r["success"])
        self.assertIn("NUEVA", r["reason"])

    def test_doble_click_idempotente(self):
        iid = self._seed("NUEVA")
        storage.update_incident_state_atomic(iid, "ASIGNADA", self.ENC, ["NUEVA"], action="tomar")
        r = storage.update_incident_state_atomic(iid, "ASIGNADA", self.ENC, ["NUEVA"], action="tomar")
        self.assertFalse(r["success"])

    def test_get_incident_inexistente(self):
        self.assertIsNone(storage.get_incident(99999))
```

También actualizar `_seed_incident` (línea 23) para que su default sea `estado="NUEVA"`.

- [ ] **Step 2: Correr y verificar que falla**

Run: `venv/bin/pytest tests/test_incident_actions.py::TestStorageTransitions -q`
Expected: FAIL (`update_incident_state_atomic` no acepta `action`/`assignee_telegram_id`).

- [ ] **Step 3: Reescribir `update_incident_state_atomic`**

Reemplazar la función completa (`storage/events.py:67-162`) por:

```python
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
    import storage
    actor_tid = actor.get("telegram_id", 0)
    actor_name = actor.get("nombre")
    actor_role = actor.get("rol", "EMPLEADO")
    action_name = action or _ACTION_FROM_STATE.get(new_state, str(new_state).lower())

    db_path = storage.DB_PATH
    db_path.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    con.isolation_level = None
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
                "UPDATE classifications SET estado=?, assigned_to_telegram_id=?, assigned_at=COALESCE(assigned_at, ?) WHERE id=?",
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
                "UPDATE classifications SET estado=?, closed_at=?, closed_by=?, resolution_time_minutes=? WHERE id=?",
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
```

También en el mapa `_ACTION_FROM_STATE` (líneas 14-18) actualizar para los nuevos estados:

```python
_ACTION_FROM_STATE = {
    IncidentState.ASIGNADA: "asignar",
    IncidentState.EN_PROCESO: "comenzar",
    IncidentState.RESUELTA: "terminado",
    IncidentState.CERRADA: "validar",
    IncidentState.CANCELADA: "cancelar",
}
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `venv/bin/pytest tests/test_incident_actions.py::TestStorageTransitions -q`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add storage/events.py tests/test_incident_actions.py
git commit -m "feat(storage): transiciones con acción explícita + trazabilidad asignar/resolver/validar/cancelar"
```

---

## Task 4: Permisos — gestión vs. ejecución y targets de asignación

**Files:**
- Modify: `permissions.py` (añadir funciones; no romper las existentes)
- Test: `tests/test_permissions.py` (añadir bloque al final)

- [ ] **Step 1: Escribir los tests que fallan**

Añadir al final de `tests/test_permissions.py`:

```python
from permissions import can_do_action, assignable_targets, assignable_departments

EMP_MANT = {"telegram_id": 5001, "nombre": "Andrei", "departamento": "MANTENIMIENTO", "rol": "EMPLEADO"}
ENC_MANT = EMPLOYEES[2001]
GERENTE = EMPLOYEES[3001]

INC_ASIGNADA_A_ANDREI = {"categoria": "MANTENIMIENTO", "assigned_to_telegram_id": 5001}
INC_ASIGNADA_A_OTRO = {"categoria": "MANTENIMIENTO", "assigned_to_telegram_id": 9998}


def test_asignado_puede_comenzar_su_tarea():
    assert can_do_action(EMP_MANT, INC_ASIGNADA_A_ANDREI, "comenzar") is True
    assert can_do_action(EMP_MANT, INC_ASIGNADA_A_ANDREI, "terminado") is True


def test_empleado_no_asignado_no_puede_ejecutar():
    assert can_do_action(EMP_MANT, INC_ASIGNADA_A_OTRO, "comenzar") is False


def test_empleado_no_puede_gestionar_aunque_sea_asignado():
    assert can_do_action(EMP_MANT, INC_ASIGNADA_A_ANDREI, "validar") is False
    assert can_do_action(EMP_MANT, INC_ASIGNADA_A_ANDREI, "asignar") is False


def test_encargado_puede_gestionar_su_depto():
    assert can_do_action(ENC_MANT, {"categoria": "MANTENIMIENTO"}, "asignar") is True
    assert can_do_action(ENC_MANT, {"categoria": "LIMPIEZA"}, "asignar") is False


def test_gerente_puede_todo():
    assert can_do_action(GERENTE, {"categoria": "LIMPIEZA"}, "validar") is True


def test_assignable_targets_encargado_su_depto():
    emps = {
        5001: EMP_MANT,
        2001: ENC_MANT,
        2002: EMPLOYEES[2002],  # HK
        1001: EMPLOYEES[1001],  # SPA empleado
    }
    targets = dict(assignable_targets(ENC_MANT, emps, "MANTENIMIENTO"))
    assert 5001 in targets and 2001 in targets
    assert 2002 not in targets and 1001 not in targets


def test_assignable_departments_gerente_lista_todos():
    emps = {5001: EMP_MANT, 2002: EMPLOYEES[2002]}
    depts = assignable_departments(GERENTE, emps)
    assert "MANTENIMIENTO" in depts and "HOUSEKEEPING" in depts
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `venv/bin/pytest tests/test_permissions.py -q`
Expected: FAIL (`ImportError: can_do_action`).

- [ ] **Step 3: Añadir funciones a `permissions.py`**

Añadir al final del archivo (después de `can_query_department`):

```python
from config.transitions import MANAGEMENT_ACTIONS, EXECUTION_ACTIONS


def _is_assignee(user: dict, incident: dict) -> bool:
    assigned = incident.get("assigned_to_telegram_id")
    if assigned is None:
        return False
    try:
        return int(assigned) == int(user.get("telegram_id", -1))
    except (TypeError, ValueError):
        return False


def can_do_action(user: dict, incident: dict, action: str) -> bool:
    """Permiso unificado por acción.

    - Acciones de gestión (asignar/tomar/reasignar/validar/reabrir/cancelar):
      solo manager con alcance sobre la incidencia (`can_act_on_incident`).
    - Acciones de ejecución (comenzar/terminado): el asignado, o un manager.
    """
    if action in EXECUTION_ACTIONS:
        return _is_assignee(user, incident) or can_act_on_incident(user, incident)
    if action in MANAGEMENT_ACTIONS:
        return can_act_on_incident(user, incident)
    return False


def assignable_targets(actor: dict, employees: dict, departamento: str) -> list[tuple[int, dict]]:
    """Empleados y encargados de `departamento` a quienes se les puede asignar una tarea."""
    out = []
    for tid, emp in employees.items():
        if emp.get("departamento") == departamento and emp.get("rol", Role.EMPLEADO) in (Role.EMPLEADO, Role.ENCARGADO):
            out.append((tid, emp))
    return out


def assignable_departments(actor: dict, employees: dict) -> list[str]:
    """Departamentos a los que el actor puede asignar (solo el gerente usa el menú cross-depto)."""
    return sorted({
        emp.get("departamento") for emp in employees.values()
        if emp.get("departamento") and emp.get("rol", Role.EMPLEADO) in (Role.EMPLEADO, Role.ENCARGADO)
    })
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `venv/bin/pytest tests/test_permissions.py -q`
Expected: PASS (todos, incluyendo los 7 nuevos).

- [ ] **Step 5: Commit**

```bash
git add permissions.py tests/test_permissions.py
git commit -m "feat(permissions): can_do_action (gestión vs ejecución) + targets de asignación"
```

---

## Task 5: Teclados — estado, picker de persona y menú de departamento

**Files:**
- Modify: `notifier/format.py:20-31` (`build_keyboard_for_state`) + añadir 2 funciones
- Modify: `notifier/__init__.py` (exportar las 2 nuevas)
- Test: `tests/test_incident_actions.py` (reescribir clase `TestKeyboard`)

- [ ] **Step 1: Reescribir los tests de teclado**

Reemplazar la clase `TestKeyboard` (líneas 127-162) por:

```python
class TestKeyboard(unittest.TestCase):

    def _callbacks(self, kb):
        return [b.callback_data for row in kb.inline_keyboard for b in row]

    def test_keyboard_nueva(self):
        kb = build_keyboard_for_state(42, "NUEVA")
        cbs = self._callbacks(kb)
        self.assertIn("incident_action:42:asignar", cbs)
        self.assertIn("incident_action:42:tomar", cbs)
        self.assertIn("incident_action:42:cancelar", cbs)

    def test_keyboard_asignada(self):
        kb = build_keyboard_for_state(42, "ASIGNADA")
        cbs = self._callbacks(kb)
        self.assertIn("incident_action:42:comenzar", cbs)
        self.assertIn("incident_action:42:reasignar", cbs)

    def test_keyboard_en_proceso(self):
        kb = build_keyboard_for_state(42, "EN_PROCESO")
        self.assertIn("incident_action:42:terminado", self._callbacks(kb))

    def test_keyboard_resuelta(self):
        cbs = self._callbacks(build_keyboard_for_state(42, "RESUELTA"))
        self.assertIn("incident_action:42:validar", cbs)
        self.assertIn("incident_action:42:reabrir", cbs)

    def test_keyboard_cerrada_none(self):
        self.assertIsNone(build_keyboard_for_state(42, "CERRADA"))

    def test_keyboard_cancelada_none(self):
        self.assertIsNone(build_keyboard_for_state(42, "CANCELADA"))

    def test_callback_dentro_limite(self):
        kb = build_keyboard_for_state(9999, "NUEVA")
        for cb in self._callbacks(kb):
            self.assertLessEqual(len(cb.encode()), 64)


class TestAssignKeyboards(unittest.TestCase):
    def test_assign_keyboard_lista_personas_y_para_mi(self):
        from notifier import build_assign_keyboard
        kb = build_assign_keyboard(7, [(222222222, "Andrei"), (444444444, "Carlos")])
        cbs = [b.callback_data for row in kb.inline_keyboard for b in row]
        self.assertIn("assign_to:7:222222222", cbs)
        self.assertIn("assign_to:7:444444444", cbs)
        self.assertIn("incident_action:7:tomar", cbs)  # botón "Para mí"

    def test_dept_menu_keyboard(self):
        from notifier import build_dept_menu_keyboard
        kb = build_dept_menu_keyboard(7, ["MANTENIMIENTO", "HOUSEKEEPING"])
        cbs = [b.callback_data for row in kb.inline_keyboard for b in row]
        self.assertIn("assign_dept:7:MANTENIMIENTO", cbs)
        self.assertIn("assign_dept:7:HOUSEKEEPING", cbs)
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `venv/bin/pytest tests/test_incident_actions.py::TestKeyboard tests/test_incident_actions.py::TestAssignKeyboards -q`
Expected: FAIL.

- [ ] **Step 3: Reescribir `build_keyboard_for_state` y añadir las 2 funciones**

Reemplazar `build_keyboard_for_state` (`notifier/format.py:20-31`) por:

```python
def build_keyboard_for_state(incident_id: int, estado: str) -> InlineKeyboardMarkup | None:
    cb = lambda action: f"incident_action:{incident_id}:{action}"
    buttons_by_state = {
        IncidentState.NUEVA:      [[("👤 Asignar", cb("asignar")), ("🙋 Tomar", cb("tomar"))],
                                   [("❌ Cancelar", cb("cancelar"))]],
        IncidentState.ASIGNADA:   [[("⏳ Comenzar", cb("comenzar")), ("🔄 Reasignar", cb("reasignar"))],
                                   [("❌ Cancelar", cb("cancelar"))]],
        IncidentState.EN_PROCESO: [[("✅ Trabajo terminado", cb("terminado"))],
                                   [("🔄 Reasignar", cb("reasignar")), ("❌ Cancelar", cb("cancelar"))]],
        IncidentState.RESUELTA:   [[("✅ Validar y cerrar", cb("validar")), ("↩️ Reabrir", cb("reabrir"))],
                                   [("❌ Cancelar", cb("cancelar"))]],
    }
    rows = buttons_by_state.get(estado)
    if not rows:
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=data) for label, data in row] for row in rows]
    )


def build_assign_keyboard(incident_id: int, targets: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """Picker de persona. `targets` = [(telegram_id, nombre), ...]."""
    rows = [[InlineKeyboardButton(f"👷 {nombre}", callback_data=f"assign_to:{incident_id}:{tid}")]
            for tid, nombre in targets]
    rows.append([InlineKeyboardButton("🙋 Para mí", callback_data=f"incident_action:{incident_id}:tomar")])
    return InlineKeyboardMarkup(rows)


def build_dept_menu_keyboard(incident_id: int, departamentos: list[str]) -> InlineKeyboardMarkup:
    """Menú de departamentos (solo gerente). Cada botón abre el picker de personas de ese depto."""
    rows = [[InlineKeyboardButton(f"🏷 {dept}", callback_data=f"assign_dept:{incident_id}:{dept}")]
            for dept in departamentos]
    return InlineKeyboardMarkup(rows)
```

En `notifier/__init__.py`, añadir a la importación desde `notifier.format`:

```python
from notifier.format import (
    format_notification_message,
    build_keyboard_for_state,
    build_assign_keyboard,
    build_dept_menu_keyboard,
)
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `venv/bin/pytest tests/test_incident_actions.py::TestKeyboard tests/test_incident_actions.py::TestAssignKeyboards -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add notifier/format.py notifier/__init__.py tests/test_incident_actions.py
git commit -m "feat(notifier): teclados de 6 estados + picker de persona y menú de depto"
```

---

## Task 6: Handler — routing de acciones, asignar/reasignar y assign_to/assign_dept

**Files:**
- Modify: `handlers/callback_handler.py:1-125` (`_handle_incident_action`) + nuevos handlers + `handle_callback`
- Modify: `handlers/callback_handler.py:227` (`to_state=IncidentState.NUEVA` en el evento "created")
- Test: `tests/test_incident_actions.py` (security test + nuevos) y `tests/test_callback_assign.py` (nuevo)

- [ ] **Step 1: Escribir tests de handler (asignación + permisos)**

Crear `tests/test_callback_assign.py`:

```python
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent))

import storage

EMPLOYEES = {
    222222222: {"telegram_id": 222222222, "nombre": "Andrei", "departamento": "MANTENIMIENTO", "rol": "EMPLEADO"},
    444444444: {"telegram_id": 444444444, "nombre": "Carlos", "departamento": "MANTENIMIENTO", "rol": "ENCARGADO"},
    777777777: {"telegram_id": 777777777, "nombre": "Alfredo", "departamento": "GENERAL", "rol": "GERENTE_GENERAL"},
}


def _seed(con, estado="NUEVA"):
    cur = con.execute(
        """INSERT INTO classifications
           (timestamp, employee_name, employee_dept, message, tipo, prioridad,
            categoria, ubicacion, descripcion, estado)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (datetime.now().isoformat(timespec="seconds"), "Jaime A", "MANTENIMIENTO",
         "x", "INCIDENCIA", "ALTA", "MANTENIMIENTO", "Hab 77", "ventilador roto", estado),
    )
    return cur.lastrowid


def _ctx():
    context = MagicMock()
    context.bot_data = {"employees": EMPLOYEES}
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    return context


def _query(data, from_id):
    q = MagicMock()
    q.from_user.id = from_id
    q.data = data
    q.answer = AsyncMock()
    q.edit_message_reply_markup = AsyncMock()
    q.edit_message_text = AsyncMock()
    q.edit_message_caption = AsyncMock()
    q.message.photo = None
    return q


@pytest.mark.asyncio
async def test_encargado_asigna_a_andrei(tmp_path):
    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        storage.init_db()
        with storage._conn() as con:
            iid = _seed(con)
        from handlers.callback_handler import _handle_incident_action
        # 1) Encargado pulsa "Asignar" → se muestra el picker, no transiciona
        q = _query(f"incident_action:{iid}:asignar", 444444444)
        with patch("handlers.callback_handler.notifier"), \
             patch("handlers.callback_handler.sheets_sync"):
            await _handle_incident_action(q, _ctx())
        q.edit_message_reply_markup.assert_awaited()
        assert storage.get_incident(iid)["estado"] == "NUEVA"

        # 2) Encargado elige a Andrei → ASIGNADA a 222222222
        from handlers.callback_handler import _handle_assign_to
        q2 = _query(f"assign_to:{iid}:222222222", 444444444)
        with patch("handlers.callback_handler.notifier") as nz, \
             patch("handlers.callback_handler.sheets_sync"):
            nz.format_notification_message.return_value = ("msg", None)
            nz.notify_assignee = AsyncMock()
            await _handle_assign_to(q2, _ctx())
        inc = storage.get_incident(iid)
        assert inc["estado"] == "ASIGNADA"
        assert int(inc["assigned_to_telegram_id"]) == 222222222


@pytest.mark.asyncio
async def test_empleado_asignado_puede_comenzar(tmp_path):
    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        storage.init_db()
        with storage._conn() as con:
            iid = _seed(con, estado="ASIGNADA")
            con.execute("UPDATE classifications SET assigned_to_telegram_id=222222222 WHERE id=?", (iid,))
        from handlers.callback_handler import _handle_incident_action
        q = _query(f"incident_action:{iid}:comenzar", 222222222)
        with patch("handlers.callback_handler.notifier") as nz, \
             patch("handlers.callback_handler.sheets_sync"):
            nz.format_notification_message.return_value = ("msg", None)
            nz.notify_employee_state_change = AsyncMock()
            nz.notify_managers_resolved = AsyncMock()
            await _handle_incident_action(q, _ctx())
        assert storage.get_incident(iid)["estado"] == "EN_PROCESO"


@pytest.mark.asyncio
async def test_empleado_no_asignado_no_puede_comenzar(tmp_path):
    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        storage.init_db()
        with storage._conn() as con:
            iid = _seed(con, estado="ASIGNADA")
            con.execute("UPDATE classifications SET assigned_to_telegram_id=999 WHERE id=?", (iid,))
        from handlers.callback_handler import _handle_incident_action
        q = _query(f"incident_action:{iid}:comenzar", 222222222)
        await _handle_incident_action(q, _ctx())
        q.answer.assert_awaited()
        assert "permiso" in q.answer.call_args[0][0].lower()
        assert storage.get_incident(iid)["estado"] == "ASIGNADA"
```

Además, en `tests/test_incident_actions.py`, en el security test (línea ~239) cambiar `query.data = f"incident_action:{iid}:tomar"` se mantiene, pero el estado sembrado debe ser `"NUEVA"` (línea ~233) y la aserción final `inc["estado"] == "NUEVA"`.

- [ ] **Step 2: Correr y verificar que falla**

Run: `venv/bin/pytest tests/test_callback_assign.py -q`
Expected: FAIL (`_handle_assign_to` no existe).

- [ ] **Step 3: Reescribir el handler**

Reemplazar el bloque de cabecera y `_handle_incident_action` (`handlers/callback_handler.py:7-125`) por:

```python
from config.enums import IncidentState, ReportType
from config.transitions import ACTION_TO_STATE, EXPECTED_FROM
import notifier
import permissions
import storage
import report_processor
import sheets_sync
from permissions import _incident_department


def _attach_assignee_name(incident: dict, employees: dict) -> dict:
    if incident.get("assigned_to_telegram_id"):
        a = employees.get(int(incident["assigned_to_telegram_id"]))
        if a:
            incident["_assignee_name"] = a.get("nombre", "")
    return incident


def _find_reporter(incident: dict, employees: dict) -> dict:
    reporter_name = incident.get("employee_name", "")
    return next(
        (emp for emp in employees.values() if emp.get("nombre") == reporter_name),
        {"nombre": reporter_name, "departamento": incident.get("employee_dept", "")},
    )


async def _refresh_message(query, incident, employees, actor_tid):
    display_id = storage.generate_display_id(ReportType.INCIDENCIA, incident["id"])
    reporter = _find_reporter(incident, employees)
    msg, keyboard = notifier.format_notification_message(
        incident=incident, reporter=reporter, incident_id_display=display_id,
        actual_recipient_telegram_id=actor_tid,
    )
    try:
        if query.message.photo:
            await query.edit_message_caption(caption=msg, reply_markup=keyboard)
        else:
            await query.edit_message_text(text=msg, reply_markup=keyboard)
    except Exception:
        pass
    return display_id


async def _handle_incident_action(query, context) -> None:
    """incident_action:{incident_id}:{action}. Action ∈ verbos de transición o asignar/reasignar."""
    parts = query.data.split(":")
    if len(parts) != 3:
        await query.answer("Formato de acción inválido", show_alert=True)
        return
    _, incident_id_str, action = parts
    try:
        incident_id = int(incident_id_str)
    except ValueError:
        await query.answer("Datos de acción inválidos", show_alert=True)
        return

    actor_telegram_id = query.from_user.id
    employees = context.bot_data["employees"]
    actor = employees.get(actor_telegram_id)
    incident = storage.get_incident(incident_id)
    if not actor or not incident:
        await query.answer("Error interno: datos no encontrados", show_alert=True)
        return

    if not permissions.can_do_action(actor, incident, action):
        storage.save_event(
            incident_id=incident_id, actor_telegram_id=actor_telegram_id,
            actor_name=actor.get("nombre"), actor_role=actor.get("rol"),
            action="action_rejected_no_permission",
            from_state=incident.get("estado") or "NUEVA", success=False,
            reason=f"rol {actor.get('rol')} sin permiso para {action}",
        )
        await query.answer("No tenés permisos sobre esta incidencia", show_alert=True)
        return

    # asignar/reasignar abren el picker, no transicionan
    if action in ("asignar", "reasignar"):
        await _show_assign_picker(query, context, incident_id, incident, actor)
        return

    new_state = ACTION_TO_STATE.get(action)
    if not new_state:
        await query.answer("Acción desconocida", show_alert=True)
        return

    result = storage.update_incident_state_atomic(
        incident_id=incident_id, new_state=new_state, actor=actor,
        expected_from_states=EXPECTED_FROM[action], action=action,
    )
    if not result["success"]:
        await query.answer(result["reason"], show_alert=True)
        return

    updated = _attach_assignee_name(storage.get_incident(incident_id), employees)
    display_id = await _refresh_message(query, updated, employees, actor_telegram_id)

    await notifier.notify_employee_state_change(
        bot=context.bot, incident=updated, new_state=new_state,
        actor_name=actor.get("nombre", ""), employees=employees,
    )
    if new_state == IncidentState.RESUELTA:
        await notifier.notify_managers_resolved(
            bot=context.bot, incident=updated, actor_name=actor.get("nombre", ""), employees=employees)

    await query.answer()
    asyncio.create_task(sheets_sync.sync_incidencia(updated, display_id, employees))


async def _show_assign_picker(query, context, incident_id, incident, actor):
    employees = context.bot_data["employees"]
    if actor.get("rol") == "GERENTE_GENERAL":
        depts = permissions.assignable_departments(actor, employees)
        kb = notifier.build_dept_menu_keyboard(incident_id, depts)
    else:
        dept = _incident_department(incident)
        targets = [(tid, e.get("nombre", "")) for tid, e in
                   permissions.assignable_targets(actor, employees, dept)]
        kb = notifier.build_assign_keyboard(incident_id, targets)
    try:
        await query.edit_message_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await query.answer("Elegí a quién asignar")


async def _handle_assign_dept(query, context) -> None:
    """assign_dept:{incident_id}:{DEPTO} — gerente eligió depto, mostrar personas."""
    _, incident_id_str, dept = query.data.split(":")
    incident_id = int(incident_id_str)
    employees = context.bot_data["employees"]
    actor = employees.get(query.from_user.id)
    incident = storage.get_incident(incident_id)
    if not actor or not incident or not permissions.can_do_action(actor, incident, "asignar"):
        await query.answer("No tenés permisos", show_alert=True)
        return
    targets = [(tid, e.get("nombre", "")) for tid, e in
               permissions.assignable_targets(actor, employees, dept)]
    kb = notifier.build_assign_keyboard(incident_id, targets)
    try:
        await query.edit_message_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await query.answer()


async def _handle_assign_to(query, context) -> None:
    """assign_to:{incident_id}:{telegram_id} — asignación efectiva."""
    _, incident_id_str, target_str = query.data.split(":")
    incident_id = int(incident_id_str)
    target_tid = int(target_str)
    employees = context.bot_data["employees"]
    actor = employees.get(query.from_user.id)
    incident = storage.get_incident(incident_id)
    if not actor or not incident or not permissions.can_do_action(actor, incident, "asignar"):
        await query.answer("No tenés permisos", show_alert=True)
        return

    result = storage.update_incident_state_atomic(
        incident_id=incident_id, new_state=IncidentState.ASIGNADA, actor=actor,
        expected_from_states=EXPECTED_FROM["asignar"], action="asignar",
        assignee_telegram_id=target_tid,
    )
    if not result["success"]:
        await query.answer(result["reason"], show_alert=True)
        return

    updated = _attach_assignee_name(storage.get_incident(incident_id), employees)
    display_id = await _refresh_message(query, updated, employees, query.from_user.id)
    await notifier.notify_assignee(bot=context.bot, incident=updated, employees=employees)
    await query.answer("Asignada")
    asyncio.create_task(sheets_sync.sync_incidencia(updated, display_id, employees))
```

En `handle_callback` (al inicio, junto a los otros `startswith`) añadir el routing:

```python
    if action.startswith("incident_action:"):
        await _handle_incident_action(query, context)
        return
    if action.startswith("assign_to:"):
        await _handle_assign_to(query, context)
        return
    if action.startswith("assign_dept:"):
        await _handle_assign_dept(query, context)
        return
```

Y en el evento "created" (línea ~227) cambiar `to_state=IncidentState.ABIERTA` por `to_state=IncidentState.NUEVA`.

- [ ] **Step 4: Correr y verificar que pasa**

Run: `venv/bin/pytest tests/test_callback_assign.py tests/test_incident_actions.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add handlers/callback_handler.py tests/test_callback_assign.py tests/test_incident_actions.py
git commit -m "feat(handler): asignar/reasignar con picker, assign_to/assign_dept, permisos por acción"
```

---

## Task 7: Notificaciones — al asignado y a los managers

**Files:**
- Modify: `notifier/state_change.py` (añadir `notify_assignee`, `notify_managers_resolved`; ampliar reporter para RESUELTA/CERRADA)
- Modify: `notifier/__init__.py` (exportar)
- Test: `tests/test_notifier.py` (añadir bloque)

- [ ] **Step 1: Escribir tests que fallan**

Añadir a `tests/test_notifier.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_notify_assignee_envia_al_asignado():
    from notifier import notify_assignee
    employees = {222222222: {"telegram_id": 222222222, "nombre": "Andrei"}}
    incident = {"id": 7, "assigned_to_telegram_id": 222222222,
                "descripcion": "ventilador roto", "ubicacion": "Hab 77"}
    bot = MagicMock()
    sent = {}
    class FakeSender:
        async def send_text(self, chat_id, text): sent["chat"] = chat_id; sent["text"] = text
    with patch("notifier.state_change.as_sender", return_value=FakeSender()), \
         patch("notifier.state_change.settings") as s:
        s.NOTIFICATION_REDIRECT_MODE = "off"
        s.ADMIN_TELEGRAM_ID = 0
        await notify_assignee(bot=bot, incident=incident, employees=employees)
    assert sent["chat"] == 222222222
    assert "ventilador" in sent["text"].lower() or "tarea" in sent["text"].lower()


@pytest.mark.asyncio
async def test_notify_managers_resolved_avisa_a_managers():
    from notifier import notify_managers_resolved
    employees = {
        444444444: {"telegram_id": 444444444, "nombre": "Carlos", "departamento": "MANTENIMIENTO", "rol": "ENCARGADO"},
        777777777: {"telegram_id": 777777777, "nombre": "Alfredo", "departamento": "GENERAL", "rol": "GERENTE_GENERAL"},
    }
    incident = {"id": 7, "categoria": "MANTENIMIENTO", "descripcion": "x", "ubicacion": "Hab 77"}
    sent = []
    class FakeSender:
        async def send_text(self, chat_id, text): sent.append(chat_id)
    with patch("notifier.state_change.as_sender", return_value=FakeSender()), \
         patch("notifier.state_change.settings") as s:
        s.NOTIFICATION_REDIRECT_MODE = "off"
        s.ADMIN_TELEGRAM_ID = 0
        await notify_managers_resolved(bot=MagicMock(), incident=incident, actor_name="Andrei", employees=employees)
    assert 444444444 in sent and 777777777 in sent
```

(Si `MagicMock` no está importado en el archivo, añadir `from unittest.mock import MagicMock`.)

- [ ] **Step 2: Correr y verificar que falla**

Run: `venv/bin/pytest tests/test_notifier.py -q`
Expected: FAIL (`notify_assignee` no existe).

- [ ] **Step 3: Añadir funciones a `notifier/state_change.py`**

Añadir al final del archivo:

```python
import asyncio
import permissions


def _resolve_recipient(tid: int):
    """Aplica redirect de testing."""
    is_redirect = settings.NOTIFICATION_REDIRECT_MODE == "admin"
    return settings.ADMIN_TELEGRAM_ID if is_redirect else tid


async def notify_assignee(bot, incident: dict, employees: dict) -> None:
    """Avisa a la persona recién asignada que tiene una tarea nueva."""
    tid = incident.get("assigned_to_telegram_id")
    if not tid:
        return
    tid = int(tid)
    display_id = storage.generate_display_id(ReportType.INCIDENCIA, incident["id"])
    desc = incident.get("descripcion", "")
    ubic = incident.get("ubicacion", "")
    text = f"🔔 Nueva tarea asignada — {display_id}\n🔧 {desc}\n📍 {ubic}\nEntrá a tus pendientes para empezar."
    sender = as_sender(bot)
    try:
        await sender.send_text(chat_id=_resolve_recipient(tid), text=text)
    except Exception:
        pass


async def notify_managers_resolved(bot, incident: dict, actor_name: str, employees: dict) -> None:
    """Avisa a los managers del depto que la incidencia fue marcada como resuelta (a validar)."""
    display_id = storage.generate_display_id(ReportType.INCIDENCIA, incident["id"])
    desc = incident.get("descripcion", "")
    text = f"✅ {actor_name} marcó como resuelto {display_id} ({desc}). Validá y cerrá cuando confirmes."
    recipients = permissions.get_notification_recipients(incident, employees)
    sender = as_sender(bot)

    async def _send(tid):
        try:
            await sender.send_text(chat_id=_resolve_recipient(tid), text=text)
        except Exception:
            pass

    await asyncio.gather(*(_send(t) for t in recipients), return_exceptions=True)
```

En `notify_employee_state_change`, añadir una rama para `RESUELTA` (antes del `else: return`) para avisar al reporter que su problema fue marcado como resuelto:

```python
    elif new_state == IncidentState.RESUELTA:
        text = f"📬 {actor_name} marcó como resuelto tu reporte {display_id}. Pendiente de validación final."
```

En `notifier/__init__.py` añadir a la import de `notifier.state_change`:

```python
from notifier.state_change import (
    notify_employee_state_change,
    notify_assignee,
    notify_managers_resolved,
)
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `venv/bin/pytest tests/test_notifier.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add notifier/state_change.py notifier/__init__.py tests/test_notifier.py
git commit -m "feat(notifier): aviso al asignado + aviso de validación a managers"
```

---

## Task 8: Presenters — emojis, labels y formato de estados nuevos

**Files:**
- Modify: `presenters/constants.py:19-39`
- Modify: `presenters/format_incidents.py`, `presenters/format_history.py` (leer y actualizar referencias a estados/acciones)
- Test: `tests/test_traceability.py` (ajustar) + revisión manual

- [ ] **Step 1: Actualizar `presenters/constants.py`**

Reemplazar `ACTION_EMOJI` y `ACTION_LABELS` (líneas 19-39) por:

```python
ACTION_EMOJI = {
    "created": "🟢",
    "tomar": "🙋",
    "asignar": "👤",
    "reasignar": "🔄",
    "comenzar": "⏳",
    "terminado": "🔧",
    "validar": "✅",
    "reabrir": "↩️",
    "cancelar": "❌",
    "notification_sent": "🔔",
    "notification_failed": "🔕",
    "action_rejected_already_done": "❌",
    "action_rejected_no_permission": "❌",
}

ACTION_LABELS = {
    "created": "Creada",
    "tomar": "Tomada por",
    "asignar": "Asignada por",
    "reasignar": "Reasignada por",
    "comenzar": "En proceso por",
    "terminado": "Resuelta por",
    "validar": "Validada y cerrada por",
    "reabrir": "Reabierta por",
    "cancelar": "Cancelada por",
    "notification_sent": "Notificación enviada",
    "notification_failed": "Notificación fallida",
    "action_rejected_already_done": "Intento rechazado (ya en estado",
    "action_rejected_no_permission": "Intento rechazado (sin permisos)",
}
```

- [ ] **Step 2: Actualizar referencias de estado en presenters**

Leer `presenters/format_incidents.py` y `presenters/format_history.py`. Reemplazar las referencias al viejo conjunto de estados/acciones:
- `IncidentState.ABIERTA` → `IncidentState.NUEVA`.
- En `format_history.py:41` y `:79` la tupla `("tomar", "en_proceso", "cerrar")` → `("tomar", "asignar", "reasignar", "comenzar", "terminado", "validar", "reabrir", "cancelar")`.
- En `format_incidents.py:33-35`, ampliar el manejo de `EN_PROCESO` para cubrir también `RESUELTA` (mostrar "RESUELTA por {assignee}") y `CANCELADA`.

Buscar referencias residuales:

```bash
grep -rn "ABIERTA\|en_proceso\|\"proceso\"\|'proceso'\|\"cerrar\"\|'cerrar'" presenters/ handlers/ notifier/ storage/ config/
```

Cada hit debe quedar coherente con el nuevo vocabulario (estados: NUEVA/ASIGNADA/EN_PROCESO/RESUELTA/CERRADA/CANCELADA; acciones: lista de Task arriba).

- [ ] **Step 3: Correr tests afectados**

Run: `venv/bin/pytest tests/test_traceability.py tests/test_query_commands.py -q`
Expected: PASS (ajustar literales `ABIERTA`→`NUEVA` en esos tests si aparecen).

- [ ] **Step 4: Commit**

```bash
git add presenters/ tests/
git commit -m "feat(presenters): emojis/labels y formato de estados work-order"
```

---

## Task 9: Google Sheets — columnas de trazabilidad

**Files:**
- Modify: `sheets_sync.py:23-33` (headers) y `:76-105` (`_sync_incidencia_sync`)
- Test: `tests/test_sheets_sync.py` (ajustar T1/T2)

- [ ] **Step 1: Ajustar el test de sync**

En `tests/test_sheets_sync.py`, en `test_sync_incidencia_new_id_appends`, tras el append verificar la longitud de la fila:

```python
        ws.append_row.assert_called_once()
        row = ws.append_row.call_args[0][0]
        assert len(row) == 15  # A..O con las 3 columnas nuevas
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `venv/bin/pytest tests/test_sheets_sync.py -q`
Expected: FAIL (la fila tiene 12 columnas).

- [ ] **Step 3: Ampliar headers y fila en `sheets_sync.py`**

En `_HEADERS["Incidencias"]` (líneas 24-26), añadir al final de la lista:
`"Asignado por", "Resuelto por", "Validado por"`.

En `_sync_incidencia_sync`, antes de construir `row`, resolver nombres:

```python
    def _name(tid):
        if not tid or not employees:
            return ""
        e = employees.get(int(tid))
        return e.get("nombre", "") if e else ""

    assigned_by_name = _name(incident.get("assigned_by"))
    resolved_by_name = _name(incident.get("resolved_by"))
    closed_by_name = _name(incident.get("closed_by"))
```

Añadir esos tres valores al final de la lista `row` (después de la columna "Foto"):

```python
        "Sí" if incident.get("photo_path") else "No",
        assigned_by_name,
        resolved_by_name,
        closed_by_name,
    ]
```

Y cambiar el rango de update de `f"A{row_num}:L{row_num}"` a `f"A{row_num}:O{row_num}"`.

- [ ] **Step 4: Correr y verificar que pasa**

Run: `venv/bin/pytest tests/test_sheets_sync.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sheets_sync.py tests/test_sheets_sync.py
git commit -m "feat(sheets): columnas Asignado por / Resuelto por / Validado por"
```

> **Nota operativa:** la hoja real ya tiene la pestaña Incidencias con encabezados viejos; `ensure_headers` solo verifica la columna A. Tras el deploy hay que **añadir manualmente** las 3 columnas (M, N, O) o borrar la fila de encabezados para que se regenere.

---

## Task 10: E2E del ciclo completo (fakes)

**Files:**
- Modify: `tests/test_hotel_scenarios.py` (añadir escenario work-order; ajustar literales ABIERTA→NUEVA)
- Test: el propio archivo

- [ ] **Step 1: Escribir el escenario E2E**

Añadir a `tests/test_hotel_scenarios.py` un test que ejercite el flujo completo con la DB real temporal y `notifier`/`sheets_sync` fakeados (seguir el patrón de los escenarios existentes en ese archivo). Secuencia a verificar:

```
reportar(NUEVA) → encargado asigna a Andrei (ASIGNADA, assigned_to=Andrei, assigned_by=encargado)
→ Andrei comenzar (EN_PROCESO) → Andrei terminado (RESUELTA, resolved_by=Andrei)
→ encargado validar (CERRADA, closed_by=encargado, resolution_time != None)
```

Y un segundo test del camino de rechazo: empleado **no** asignado intenta `comenzar` → estado sin cambios + answer con "permiso".
Y un tercero: `reabrir` desde RESUELTA → ASIGNADA conservando `assigned_to`.

Usar las funciones `_handle_incident_action` / `_handle_assign_to` con `MagicMock` de query como en `tests/test_callback_assign.py`.

- [ ] **Step 2: Correr y verificar que pasa**

Run: `venv/bin/pytest tests/test_hotel_scenarios.py -q`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_hotel_scenarios.py
git commit -m "test(e2e): ciclo work-order completo reportar→asignar→comenzar→resuelto→validar"
```

---

## Task 11: Barrido final, suite completa y docs

**Files:**
- Modify: `CLAUDE.md` (invariantes de estado), cualquier test residual con `ABIERTA`

- [ ] **Step 1: Barrer literales viejos**

```bash
grep -rn "ABIERTA" --include=*.py . | grep -v ".pyc"
```
Cada hit en código o tests debe migrarse a `NUEVA` (salvo la migración de datos de Task 2, que la menciona a propósito).

- [ ] **Step 2: Suite normal verde**

Run: `venv/bin/pytest -q`
Expected: PASS (los 178 previos + los nuevos; 5 integration deselected).

- [ ] **Step 3: Actualizar CLAUDE.md**

En la sección **Invariantes críticos**, actualizar el callback/estado:
- Mencionar los 6 estados y que `config/transitions.py` es la fuente de verdad de la máquina de estados.
- Aclarar callbacks: `incident_action:{id}:{action}` + `assign_to:{id}:{tid}` + `assign_dept:{id}:{depto}` (todos 3 partes).
- Nota sobre `can_do_action` (gestión vs ejecución; el asignado puede ejecutar su tarea).

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: invariantes de la máquina de estados work-order en CLAUDE.md"
```

---

## Self-Review (verificación del autor del plan)

**Cobertura del spec:**
- 6 estados + CANCELADA → Task 1. ✅
- Sin REVISADA → no se crea. ✅
- Doble paso RESUELTA/CERRADA → Task 3 (terminado/validar) + Task 6 (botones) + Task 7 (aviso a managers). ✅
- Permisos: asignado ejecuta, manager gestiona → Task 4 + Task 6. ✅
- Asignación por botones; gerente cross-depto → Task 5 (keyboards) + Task 6 (picker/dept). ✅
- Notificaciones (asignado/managers/reporter) → Task 7. ✅
- Trazabilidad (assigned_by/resolved_by/closed_by/cancelled_by) → Task 2 (columnas) + Task 3 (escritura) + Task 9 (Sheets). ✅
- Callbacks 3 partes → Task 5/6 (todos verificados ≤64 bytes). ✅
- Migración ABIERTA→NUEVA → Task 2. ✅
- Reabrir → ASIGNADA conservando assignee → Task 3 + Task 10. ✅
- Testing fuerte (unit + e2e) → Tasks 1-10 con TDD + Task 10 e2e + Task 11 suite. ✅

**Consistencia de tipos/nombres:** verbos de acción idénticos en `config/transitions.py`, teclados, handler y permisos (`tomar/asignar/reasignar/comenzar/terminado/validar/reabrir/cancelar`). `update_incident_state_atomic(..., action=, assignee_telegram_id=, cancel_reason=)` usado igual en Task 3, 6. Callbacks `assign_to:{id}:{tid}` y `assign_dept:{id}:{depto}` idénticos en Task 5 y 6.

**Sin placeholders:** todo paso de código incluye el código real. Tasks 8 y 10 piden leer 2-3 archivos durante la implementación (referencias residuales y patrón e2e existente) porque su contenido exacto depende de líneas no transcritas aquí; las instrucciones son concretas (qué reemplazar por qué).
