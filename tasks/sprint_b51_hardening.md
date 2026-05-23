# Sprint B.5.1 — Hardening Pre-Piloto

> **Plan — esperando luz verde antes de tocar código.**

---

## REPORTE FIX #1 — Seguridad de callbacks

### Veredicto: **BUG CONFIRMADO**

**Archivo:** `handlers/callback_handler.py`, función `_handle_incident_action`

### Cómo ocurre

Los botones de acción sobre incidencias se construyen en `notifier.py:27`:

```python
cb = lambda action: f"incident_action:{incident_id}:{action}:{actor_telegram_id}"
# Ejemplo: "incident_action:3:tomar:444444444"
```

En `callback_handler.py:28-30`:

```python
_, incident_id_str, sub_action, actor_id_str = parts
actor_telegram_id = int(actor_id_str)   # ← ID del ACTOR viene del callback_data
...
actor = employees.get(actor_telegram_id)  # ← lookup con ID del callback, no del presionador
```

**El actor se identifica por el ID embebido en `callback_data`, NO por `query.from_user.id`.**

### Impacto real

Telegram no permite editar callback_data de botones recibidos en el cliente oficial, así que el ataque requeriría un cliente modificado o una sesión de prueba. Aun así, el diseño es incorrecto: la identidad del actor no puede venir de un campo controlable por el cliente. Ningún callback debería establecer quién actúa.

### Callbacks revisados

| Callback | ¿Usa actor embebido? | ¿Bug? |
|---|---|---|
| `incident_action:*` (tomar/proceso/cerrar) | Sí — `actor_id_str` de `parts[3]` | **SÍ** |
| `report_confirm_all` | No — usa `query.from_user.id` (línea 122) | ✓ |
| `report_correct` | No — no identifica actor | ✓ |
| `confirm` | No — usa `get_employee(update, context)` | ✓ |
| `correct` | No — no identifica actor | ✓ |

### Fix elegido: Opción A

Eliminar el `actor_telegram_id` del `callback_data`. El actor siempre sale de `query.from_user.id`. El nuevo formato de callback es:

```
incident_action:{incident_id}:{sub_action}
# Ejemplo: "incident_action:3:tomar"
```

---

## Plan de implementación

### Fix #1 — Seguridad de callbacks

**Archivos a modificar:**
- `notifier.py:27` — la lambda que construye el callback_data
- `handlers/callback_handler.py:22-34` — el parser y la línea de actor lookup
- `tests/test_incident_actions.py` — actualizar `TestKeyboard` + nuevo test de seguridad

---

- [ ] **1.1 — Escribir el test de seguridad (debe fallar antes del fix)**

Agregar al final de `tests/test_incident_actions.py`, después de la clase `TestPermissions`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_callback_actor_is_from_user_id(tmp_path):
    """Actor identity comes from query.from_user.id — unauthorized user is rejected."""
    db_path = tmp_path / "test.db"
    with patch.object(storage, "DB_PATH", db_path):
        storage.init_db()
        with storage._conn() as con:
            from datetime import datetime
            cur = con.execute(
                """INSERT INTO classifications
                   (timestamp, employee_name, employee_dept, message, tipo, prioridad,
                    categoria, ubicacion, descripcion, estado)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (datetime.now().isoformat(timespec="seconds"),
                 "Ana", "HK", "t", "INCIDENCIA", "ALTA",
                 "MANTENIMIENTO", "Hab 1", "test", "ABIERTA"),
            )
            iid = cur.lastrowid

        EMPLEADOS = {
            111111111: {"nombre": "María", "departamento": "HOUSEKEEPING",
                        "rol": "EMPLEADO", "telegram_id": 111111111},
            444444444: {"nombre": "Carlos", "departamento": "MANTENIMIENTO",
                        "rol": "ENCARGADO", "telegram_id": 444444444},
        }

        query = MagicMock()
        query.from_user.id = 111111111      # EMPLEADO — sin permisos de acción
        query.data = f"incident_action:{iid}:tomar"  # formato 3 partes (post-fix)
        query.answer = AsyncMock()

        context = MagicMock()
        context.bot_data = {"employees": EMPLEADOS}

        from handlers.callback_handler import _handle_incident_action
        await _handle_incident_action(query, context)

        # El EMPLEADO debe ser rechazado por sus permisos
        query.answer.assert_called_once()
        answer_text = query.answer.call_args[0][0]
        assert "permisos" in answer_text.lower()

        # La incidencia no debe haber cambiado de estado
        inc = storage.get_incident(iid)
        assert inc["estado"] == "ABIERTA"
```

- [ ] **1.2 — Correr el test para confirmar que falla**

```bash
pytest tests/test_incident_actions.py::test_callback_actor_is_from_user_id -v
```

Esperado: FAIL (con código antiguo, el parser espera 4 partes y responde "Formato de acción inválido", que no contiene "permisos")

- [ ] **1.3 — Cambiar el formato del callback en notifier.py:27**

```python
# Antes:
cb = lambda action: f"incident_action:{incident_id}:{action}:{actor_telegram_id}"

# Después:
cb = lambda action: f"incident_action:{incident_id}:{action}"
```

- [ ] **1.4 — Actualizar el parser en callback_handler.py:22-34**

```python
# Antes (líneas 22-34):
async def _handle_incident_action(query, context) -> None:
    """Handles incident_action:{incident_id}:{sub_action}:{actor_telegram_id} callbacks."""
    parts = query.data.split(":")
    if len(parts) != 4:
        await query.answer("Formato de acción inválido", show_alert=True)
        return

    _, incident_id_str, sub_action, actor_id_str = parts
    try:
        incident_id = int(incident_id_str)
        actor_telegram_id = int(actor_id_str)
    except ValueError:
        await query.answer("Datos de acción inválidos", show_alert=True)
        return

# Después:
async def _handle_incident_action(query, context) -> None:
    """Handles incident_action:{incident_id}:{sub_action} callbacks."""
    parts = query.data.split(":")
    if len(parts) != 3:
        await query.answer("Formato de acción inválido", show_alert=True)
        return

    _, incident_id_str, sub_action = parts
    try:
        incident_id = int(incident_id_str)
    except ValueError:
        await query.answer("Datos de acción inválidos", show_alert=True)
        return

    actor_telegram_id = query.from_user.id
```

(La variable `actor_telegram_id` mantiene el nombre — el resto del código ya la usa correctamente.)

- [ ] **1.5 — Actualizar las aserciones de formato en TestKeyboard**

En `tests/test_incident_actions.py`, clase `TestKeyboard`, cambiar las aserciones de `callback_data`:

```python
# test_keyboard_abierta_tres_botones
# Antes:
self.assertIn("incident_action:42:tomar:444444444", callbacks)
self.assertIn("incident_action:42:proceso:444444444", callbacks)
self.assertIn("incident_action:42:cerrar:444444444", callbacks)
# Después:
self.assertIn("incident_action:42:tomar", callbacks)
self.assertIn("incident_action:42:proceso", callbacks)
self.assertIn("incident_action:42:cerrar", callbacks)

# test_keyboard_en_proceso_un_boton
# Antes:
self.assertEqual(kb.inline_keyboard[0][0].callback_data, "incident_action:42:cerrar:444444444")
# Después:
self.assertEqual(kb.inline_keyboard[0][0].callback_data, "incident_action:42:cerrar")
```

- [ ] **1.6 — Correr todos los tests del módulo**

```bash
pytest tests/test_incident_actions.py -v
```

Esperado: todos pasan, incluyendo el nuevo `test_callback_actor_is_from_user_id`

- [ ] **1.7 — Correr suite completa para verificar regresiones**

```bash
pytest tests/ -v
```

Esperado: 100% verde

- [ ] **1.8 — Commit**

```bash
git add notifier.py handlers/callback_handler.py tests/test_incident_actions.py
git commit -m "fix: actor identity from query.from_user.id, not callback_data"
```

---

### Fix #2 — Lazy init del cliente Gemini

**Archivos a modificar:**
- `classifier.py:8-9` — reemplazar client global por patrón lazy
- `classifier.py:125` — usar `_get_client()` en vez de `client`
- `dashboard.py:5` — actualizar import
- `dashboard.py:214,249` — actualizar uso del cliente

---

- [ ] **2.1 — Reemplazar client global en classifier.py**

```python
# Antes (líneas 8-9):
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# Después:
_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY no encontrada en .env")
        _client = genai.Client(api_key=api_key)
    return _client
```

- [ ] **2.2 — Actualizar la llamada en classify()**

```python
# classifier.py línea ~125
# Antes:
response = client.models.generate_content(

# Después:
response = _get_client().models.generate_content(
```

- [ ] **2.3 — Actualizar dashboard.py**

```python
# Línea 5 — Antes:
from classifier import classify, client, SYSTEM_PROMPT

# Después:
from classifier import classify, _get_client, SYSTEM_PROMPT
```

Y en los dos call sites (líneas ~214 y ~249):

```python
# Antes:
response = client.models.generate_content(

# Después:
response = _get_client().models.generate_content(
```

- [ ] **2.4 — Verificar que import sin API key no explota**

```bash
GEMINI_API_KEY="" python -c "import classifier; print('OK')"
```

Esperado: `OK` (sin exception)

- [ ] **2.5 — Verificar que el error se lanza al usar la función**

```bash
GEMINI_API_KEY="" python -c "
from classifier import _get_client
try:
    _get_client()
    print('ERROR: debería haber fallado')
except RuntimeError as e:
    print(f'OK: {e}')
"
```

Esperado: `OK: GEMINI_API_KEY no encontrada en .env`

- [ ] **2.6 — Correr suite completa**

```bash
pytest tests/ -v
```

Esperado: 100% verde

- [ ] **2.7 — Commit**

```bash
git add classifier.py dashboard.py
git commit -m "fix: lazy init Gemini client in classifier.py to avoid import-time KeyError"
```

---

### Fix #3 — Sacar tests con red de la suite default

**Archivos a modificar:**
- `test_brain.py` (en raíz del proyecto)
- `pytest.ini`

**Confirmación de alcance:** `evaluate.py` y `evaluate_audio.py` son scripts (tienen función `main()`, no `def test_*`) — pytest no los colecta y no requieren cambios.

**Situación actual:** `test_brain.py` corre 5 llamadas a `process_message()` a nivel de módulo (líneas 33, 50, 64, 73, 82). Pytest importa el archivo durante la fase de collection, disparando llamadas reales a Gemini y Groq. Causa: colección lenta (~16 seg) y falla sin red.

---

- [ ] **3.1 — Reescribir test_brain.py con funciones pytest marcadas**

Reemplazar el contenido completo de `test_brain.py` con:

```python
"""Tests de integración — requieren red y API keys reales. Correr con: pytest -m integration"""
import pytest
from pathlib import Path
from brain import process_message
from audio_test_cases import AUDIO_TEST_CASES

AUDIOS_DIR = Path(__file__).parent / "audios"
MARIA = {"nombre": "María", "departamento": "HOUSEKEEPING", "idioma": "es"}
ANDREI = {"nombre": "Andrei", "departamento": "MANTENIMIENTO", "idioma": "ro"}


@pytest.mark.integration
def test_texto_espanol():
    result = process_message("Hay un goteo en el aire acondicionado de la 204", MARIA)
    meta = result.get("_meta", {})
    assert result.get("tipo") == "INCIDENCIA"
    assert meta.get("input_type") == "text"
    assert meta.get("transcription") is None
    assert meta.get("error") is None


@pytest.mark.integration
def test_audio_espanol():
    audio_es = AUDIOS_DIR / AUDIO_TEST_CASES[0]["filename"]
    if not audio_es.exists():
        pytest.skip(f"Archivo de audio no encontrado: {AUDIO_TEST_CASES[0]['filename']}")
    result = process_message(str(audio_es), MARIA, is_audio=True)
    meta = result.get("_meta", {})
    assert result.get("tipo") != "ERROR"
    assert meta.get("input_type") == "audio"
    assert meta.get("transcription") is not None
    assert meta.get("audio_language_detected") == "Spanish"


@pytest.mark.integration
def test_audio_rumano():
    audio_ro = AUDIOS_DIR / AUDIO_TEST_CASES[4]["filename"]
    if not audio_ro.exists():
        pytest.skip(f"Archivo de audio no encontrado: {AUDIO_TEST_CASES[4]['filename']}")
    result = process_message(str(audio_ro), ANDREI, is_audio=True, language_hint="ro")
    meta = result.get("_meta", {})
    assert result.get("tipo") != "ERROR"
    assert meta.get("audio_language_detected") == "Romanian"
    assert result.get("descripcion") is not None


@pytest.mark.integration
def test_audio_inexistente():
    result = process_message("audios/no_existe.flac", MARIA, is_audio=True)
    meta = result.get("_meta", {})
    assert result.get("tipo") == "ERROR"
    assert meta.get("error") is not None
    assert meta.get("input_type") == "audio"


@pytest.mark.integration
def test_texto_vacio():
    result = process_message("", MARIA)
    meta = result.get("_meta", {})
    assert result.get("tipo") in ("ERROR", "NO_REPORTE")
    assert meta.get("input_type") == "text"
```

- [ ] **3.2 — Actualizar pytest.ini**

```ini
[pytest]
asyncio_mode = auto
markers =
    integration: tests que hacen llamadas reales a APIs externas (requieren red y API keys)
addopts = -m "not integration"
# Para correr los integration: pytest -m integration
```

- [ ] **3.3 — Verificar que la suite default no corre los tests de red**

```bash
pytest --collect-only -q 2>&1 | grep "test_brain\|integration"
```

Esperado: los tests de `test_brain.py` aparecen en la colección pero no se ejecutan con `pytest` plain.

```bash
time pytest tests/ -v
```

Esperado: mismo resultado que antes, sin los 5 tests de integración, colección rápida (< 5 seg).

- [ ] **3.4 — Verificar que los integration se pueden correr explícitamente**

```bash
pytest -m integration -v --no-header 2>&1 | head -5
```

Esperado: los 5 tests de test_brain.py son encontrados y ejecutados (si hay red y API keys).

- [ ] **3.5 — Commit**

```bash
git add test_brain.py pytest.ini
git commit -m "fix: wrap test_brain.py in @pytest.mark.integration to avoid API calls during collection"
```

---

### Fix #4 — Deprecar update_incident_state no-atómica

**Archivos a modificar:**
- `tests/test_incident_actions.py` — clase `TestStorageTransitions`: migrar 8 call sites
- `storage.py:341-405` — eliminar `update_incident_state`

**Call sites confirmados:** SOLO en `tests/test_incident_actions.py` (8 llamadas). Ningún código de aplicación la usa. Todos los handlers usan `update_incident_state_atomic`.

**Diferencias de firma:**
- Vieja: `update_incident_state(incident_id, new_state, actor_telegram_id) → {success, new_state, reason}`
- Nueva: `update_incident_state_atomic(incident_id, new_state, actor_dict, expected_from_states) → {success, from_state, to_state, reason}`

Nota de clave de resultado: `result["new_state"]` → `result["to_state"]`

---

- [ ] **4.1 — Migrar TestStorageTransitions a usar update_incident_state_atomic**

Al inicio de la clase `TestStorageTransitions`, agregar el actor constante:

```python
ACTOR = {"telegram_id": 444444444, "nombre": "Carlos Encargado Mant", "rol": "ENCARGADO"}
ACTOR_B = {"telegram_id": 777777777, "nombre": "Alfredo Gerente", "rol": "GERENTE_GENERAL"}
```

Luego reemplazar cada call site (en las 7 funciones de test):

```python
# test_tomar_abierta_cambia_a_asignada
# Antes:
result = storage.update_incident_state(iid, "ASIGNADA", 444444444)
self.assertEqual(result["new_state"], "ASIGNADA")
# Después:
result = storage.update_incident_state_atomic(iid, "ASIGNADA", self.ACTOR, ["ABIERTA"])
self.assertEqual(result["to_state"], "ASIGNADA")

# test_tomar_asignada_falla
# Antes:
result = storage.update_incident_state(iid, "ASIGNADA", 444444444)
# Después:
result = storage.update_incident_state_atomic(iid, "ASIGNADA", self.ACTOR, ["ABIERTA"])

# test_proceso_desde_abierta_asigna_actor
# Antes:
result = storage.update_incident_state(iid, "EN_PROCESO", 444444444)
# Después:
result = storage.update_incident_state_atomic(iid, "EN_PROCESO", self.ACTOR, ["ABIERTA", "ASIGNADA"])

# test_proceso_desde_asignada_no_toca_assignee
# Antes:
storage.update_incident_state(iid, "ASIGNADA", 444444444)
storage.update_incident_state(iid, "EN_PROCESO", 777777777)
# Después:
storage.update_incident_state_atomic(iid, "ASIGNADA", self.ACTOR, ["ABIERTA"])
storage.update_incident_state_atomic(iid, "EN_PROCESO", self.ACTOR_B, ["ABIERTA", "ASIGNADA"])

# test_cerrar_desde_asignada_guarda_tiempos
# Antes:
storage.update_incident_state(iid, "ASIGNADA", 444444444)
result = storage.update_incident_state(iid, "CERRADA", 444444444)
# Después:
storage.update_incident_state_atomic(iid, "ASIGNADA", self.ACTOR, ["ABIERTA"])
result = storage.update_incident_state_atomic(iid, "CERRADA", self.ACTOR, ["ABIERTA", "ASIGNADA", "EN_PROCESO"])

# test_cerrar_cerrada_falla
# Antes:
result = storage.update_incident_state(iid, "CERRADA", 444444444)
# Después:
result = storage.update_incident_state_atomic(iid, "CERRADA", self.ACTOR, ["ABIERTA", "ASIGNADA", "EN_PROCESO"])

# test_cerrar_desde_abierta
# Antes:
result = storage.update_incident_state(iid, "CERRADA", 444444444)
self.assertEqual(result["new_state"], "CERRADA")
# Después:
result = storage.update_incident_state_atomic(iid, "CERRADA", self.ACTOR, ["ABIERTA", "ASIGNADA", "EN_PROCESO"])
self.assertEqual(result["to_state"], "CERRADA")
```

- [ ] **4.2 — Correr tests para verificar que todos pasan antes de borrar la función**

```bash
pytest tests/test_incident_actions.py::TestStorageTransitions -v
```

Esperado: los 7 tests pasan con la nueva implementación atómica

- [ ] **4.3 — Eliminar update_incident_state de storage.py (líneas 341-405)**

Borrar la función completa `update_incident_state` (desde `def update_incident_state(` hasta `return {"success": True, "new_state": new_state, "reason": None}`).

- [ ] **4.4 — Verificar que no quedan importaciones ni usos**

```bash
grep -rn "update_incident_state[^_]" . --include="*.py" | grep -v "__pycache__"
```

Esperado: sin resultados (solo puede aparecer en comentarios o en la definición de la función atómica, que termina con `_atomic`)

- [ ] **4.5 — Correr suite completa**

```bash
pytest tests/ -v
```

Esperado: 100% verde

- [ ] **4.6 — Commit**

```bash
git add storage.py tests/test_incident_actions.py
git commit -m "fix: remove non-atomic update_incident_state; all state changes now go through atomic version"
```

---

## Criterio de éxito

- [ ] `pytest tests/` sin red → 100% verde, colección < 5 seg
- [ ] `pytest -m integration` con red → corre los 5 tests de test_brain.py
- [ ] `python -c "import classifier"` sin GEMINI_API_KEY → no explota
- [ ] `grep -rn "update_incident_state[^_]" . --include="*.py"` → sin resultados
- [ ] Ningún callback de incidencia embebe el ID del actor en callback_data

---

## Lecciones a agregar en tasks/lessons.md

1. **Tests con efectos externos en import-time:** código a nivel de módulo en archivos `test_*.py` se ejecuta durante la fase de colección de pytest, disparando costos reales (API calls, latencia, dinero) aunque los tests no se pidan. Todo código con efectos externos debe vivir dentro de funciones `test_*`.

2. **Identidad del actor en callbacks de Telegram:** el actor de una acción SIEMPRE es `query.from_user.id`. Nunca confiar en un ID embebido en `callback_data` para establecer identidad — ese dato viene del cliente y puede ser manipulado. El `callback_data` solo debe llevar identidad de *objetos* (IDs de incidencias, IDs de recursos), nunca del *sujeto* (quién actúa).

---

## Fuera de alcance (backlog)

- `normalize_classification()` / validación de esquema del JSON del LLM
- Permisos genéricos para `/hab` y `/buscar` (requiere decisión de producto)
- Extraer `_pop_followup_state` / `_pop_correction_state` a `handlers/state.py`
- Sistema de migraciones versionadas / `schema_version`
- Reorganización completa `tests/` vs `tests_integration/` (solo se separó `test_brain.py`)
