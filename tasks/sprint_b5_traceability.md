# Sprint B.5 — Trazabilidad: tabla de eventos y concurrencia segura

## Análisis del código actual

### `storage.py` — `update_incident_state`
Tiene dos conexiones separadas: una para leer el estado actual, otra para escribir.
Entre ambas hay una ventana de race condition. La solución es una transacción `BEGIN IMMEDIATE`
que bloquea el archivo SQLite para escritura desde el primer momento.

**Decisión**: mantener `update_incident_state` para que los tests de B.3 sigan pasando.
Añadir `update_incident_state_atomic` como función de producción. El `callback_handler.py` 
migra a la versión atómica.

### `notifier.py` — `send_notification_with_logging`
Actualmente llama a `save_notification` (tabla `notifications`). Hay que añadir `save_event`
al mismo punto, con `action="notification_sent"` o `"notification_failed"`.
La tabla `notifications` se queda — no la eliminamos.

### `callback_handler.py` — `_handle_incident_action`
Actualmente llama a `storage.update_incident_state` y solo registra el rechazo de permisos
con el propio `query.answer`. En B.5: migra a `update_incident_state_atomic` (que maneja
su propio registro de eventos) y registra también los rechazos de permisos con `save_event`.

### `callback_handler.py` — `handle_callback` (confirm)
El `save()` en el branch de `confirm` devuelve el `incident_id`. Justo después de ese `save()`,
registrar el evento `created`. El `save()` NO se modifica — el evento se registra desde el handler
donde existe el contexto del empleado (telegram_id, nombre, rol).

### `handlers/__init__.py` — `format_incident_line`
Tiene acceso a `assigned_at` y `closed_at` del incident dict (ya están en la DB desde B.3).
Usarlos para enriquecer el display sin necesitar la tabla de eventos. Esto es más simple
y no requiere queries adicionales en cada línea de lista.

---

## Decisiones de diseño

### `extra` field: TEXT con JSON
Igual que `campos_faltantes` en la tabla principal. `json.dumps(extra or {})` al guardar,
`json.loads(row["extra"] or "{}")` al leer.

### `init_events_table` dentro de `init_db`
Mismo patrón que el resto: la tabla se crea en `init_db()` con `CREATE TABLE IF NOT EXISTS`.
No hace falta llamada separada.

### `BEGIN IMMEDIATE` con `isolation_level=None`
El helper `_conn()` usa context manager que autocommit. Para la transacción atómica necesitamos
control manual. Usamos una conexión directa con `isolation_level=None` y llamadas explícitas
a `BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK`. Es la única función que hace esto.

### `expected_from_states` reemplaza el dict `invalid` de B.3
En la versión atómica, cada botón declara explícitamente desde qué estados puede actuar:
- `tomar`: ["ABIERTA"]
- `proceso`: ["ABIERTA", "ASIGNADA"]
- `cerrar`: ["ABIERTA", "ASIGNADA", "EN_PROCESO"]

Más legible y el check está dentro de la transacción locked.

### Timeline solo en notificación de CERRADA
`notify_employee_state_change` construye el timeline completo solo cuando `new_state == "CERRADA"`.
Para ASIGNADA y EN_PROCESO, el mensaje simple es suficiente — añadir timeline en cada paso
haría el chat ruidoso. Al cierre es cuando tiene sentido el resumen completo.

---

## Pasos de implementación

### Paso 1 — `storage.py`: tabla de eventos + 4 funciones

**1a. `init_db`**: añadir la tabla y los índices dentro del bloque existente.
```sql
CREATE TABLE IF NOT EXISTS incident_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    incident_id INTEGER NOT NULL,
    actor_telegram_id INTEGER NOT NULL,
    actor_name TEXT,
    actor_role TEXT,
    action TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT,
    success INTEGER NOT NULL DEFAULT 1,
    reason TEXT,
    extra TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_incident ON incident_events(incident_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON incident_events(timestamp);
```

**1b. `save_event(incident_id, actor_telegram_id, actor_name, actor_role, action, from_state, to_state, success, reason, extra) -> int`**

**1c. `get_events_for_incident(incident_id) -> list[dict]`**
SELECT * ORDER BY timestamp ASC, id ASC (id como desempate si mismos ms).

**1d. `update_incident_state_atomic(incident_id, new_state, actor, expected_from_states) -> dict`**
- Abre conexión con `isolation_level=None`
- `BEGIN IMMEDIATE` — bloquea para escritura
- Lee estado actual
- Si `current` no está en `expected_from_states`:
  - Inserta evento `action_rejected_already_done`
  - `COMMIT`
  - Devuelve `{success: False, from_state: current, to_state: current, reason: ...}`
- Si válida: aplica UPDATE + inserta evento de acción exitosa, `COMMIT`
- Devuelve `{success: True, from_state: current, to_state: new_state, reason: None}`
- `except/finally`: ROLLBACK + close

Action names para eventos de éxito: mapear desde new_state:
`{"ASIGNADA": "tomar", "EN_PROCESO": "en_proceso", "CERRADA": "cerrar"}`

**1e. `get_incident_with_events(incident_id) -> dict | None`**
Devuelve `get_incident(incident_id)` enriquecido con `"events": get_events_for_incident(incident_id)`.

**Verificación**: tests de storage.

---

### Paso 2 — `notifier.py`: registrar eventos + timeline en notificación

**2a. `send_notification_with_logging`**: añadir `save_event` en try y except, con
`action="notification_sent"` / `"notification_failed"`. El `extra` JSON lleva:
`{"recipient": tid, "actual_recipient": actual_tid, "redirect_mode": redirect_mode}`.
`actor_telegram_id=0, actor_name="sistema"` para acciones del sistema.

**2b. `notify_employee_state_change`**: cuando `new_state == "CERRADA"`:
- Consultar `storage.get_events_for_incident(incident["id"])`
- Llamar `build_timeline_text(events)` (de handlers/__init__.py)
- Construir mensaje enriquecido con timeline

**Verificación**: tests de notifier.

---

### Paso 3 — `handlers/__init__.py`: 3 helpers nuevos + actualizar `format_incident_line`

**3a. `calculate_total_time(events) -> str`**:
Busca el evento `created` (from_state=None, action="created") y el evento `cerrar`.
Diferencia en minutos. Si < 60: "X min". Si >= 60: "Xh Ymin". Si no hay cierre: "" (vacío).

**3b. `build_timeline_text(events) -> str`**:
Filtra eventos relevantes (ignora `notification_sent/failed`). Para cada uno construye
una línea según el action:
- created → "• Reportada"
- tomar → "• Tomada por {actor_name} {tiempo}"
- en_proceso → "• En proceso por {actor_name} {tiempo}"
- cerrar → "• Resuelta por {actor_name} {tiempo}"

**3c. `format_incident_history(incident, events) -> str`**:
Genera la salida de `/historial INC-N`. Usa los emojis del spec:
- created: 🟢
- notification_sent: 🔔
- tomar: 🙋
- en_proceso: ⏳
- cerrar: ✅
- action_rejected_*: ❌

**3d. Actualizar `format_incident_line`**: usar `assigned_at` para EN_PROCESO/ASIGNADA:
```
🟠 INC-142 — ALTA — Hab 305 — Goteo en baño
   Mantenimiento · Reportada hace 1h 23min · EN_PROCESO por Carlos hace 38min
```
El `assigned_at` ya está en el incident dict. El nombre del asignado via `_resolve_assignee_name`.

**3e. Actualizar `get_help_text`**: añadir `/historial INC-N` para ENCARGADO y GERENTE_GENERAL.

**Verificación**: tests de formateo.

---

### Paso 4 — `handlers/callback_handler.py`: migrar a atómica + registrar rechazos

Cambios en `_handle_incident_action`:

```python
expected_from = {"tomar": ["ABIERTA"], "proceso": ["ABIERTA", "ASIGNADA"], "cerrar": ["ABIERTA", "ASIGNADA", "EN_PROCESO"]}

if not permissions.can_act_on_incident(actor, incident):
    storage.save_event(
        incident_id=incident_id,
        actor_telegram_id=actor_telegram_id,
        actor_name=actor.get("nombre"),
        actor_role=actor.get("rol"),
        action="action_rejected_no_permission",
        from_state=incident.get("estado") or "ABIERTA",
        success=False,
        reason=f"rol {actor.get('rol')} no tiene permiso",
    )
    await query.answer("No tenés permisos sobre esta incidencia", show_alert=True)
    return

result = storage.update_incident_state_atomic(
    incident_id=incident_id,
    new_state=state_map[sub_action],
    actor=actor,
    expected_from_states=expected_from[sub_action],
)
# resto del flujo igual
```

En `handle_callback` branch `confirm`:
```python
incident_id = save(employee, pending["original_text"], result)
if result.get("tipo") == "INCIDENCIA":
    storage.save_event(
        incident_id=incident_id,
        actor_telegram_id=employee.get("telegram_id", 0),
        actor_name=employee.get("nombre"),
        actor_role=employee.get("rol", "EMPLEADO"),
        action="created",
        to_state="ABIERTA",
        success=True,
    )
```

**Verificación**: tests de concurrencia.

---

### Paso 5 — `handlers/command_handler.py`: `/historial`

```python
async def handle_historial(update, context):
    args = context.args or []
    if not args:
        await update.message.reply_text("Usá: /historial INC-N o /historial 142")
        return
    raw = args[0].upper().removeprefix("INC-")
    try:
        incident_id = int(raw)
    except ValueError:
        await update.message.reply_text("ID inválido.")
        return
    ...
```

Permisos: `permissions.can_see_incident(user, incident)`.

**Verificación**: tests de handler.

---

### Paso 6 — `bot.py`: registrar `/historial`

Añadir `CommandHandler("historial", handle_historial)`. Un handler, una línea.

---

## Tests en `tests/test_traceability.py` — 17 mínimos

| # | Test |
|---|------|
| 1 | `save_event` con campos mínimos inserta sin error |
| 2 | `save_event` con `extra` serializa JSON y `get_events` lo deserializa |
| 3 | `get_events_for_incident` devuelve ordenado por timestamp ASC |
| 4 | `update_incident_state_atomic` ABIERTA→ASIGNADA: success + evento "tomar" |
| 5 | `update_incident_state_atomic` ASIGNADA→ASIGNADA (no en expected): rechaza + evento rejected |
| 6 | `update_incident_state_atomic` CERRADA→cualquier: rechaza, registra rechazo |
| 7 | **Test de concurrencia** con threading: dos threads, misma incidencia ABIERTA, ambas intentan "tomar". Una gana, la otra registra rechazo. Solo 1 evento "tomar" success. |
| 8 | `build_timeline_text` con eventos created+tomar+cerrar devuelve las 3 líneas |
| 9 | `build_timeline_text` filtra eventos notification_sent (no los incluye) |
| 10 | `calculate_total_time` con 83 min de diferencia devuelve "1h 23min" |
| 11 | `calculate_total_time` con menos de 1 min devuelve "menos de 1 min" |
| 12 | `calculate_total_time` sin evento cerrar devuelve "" |
| 13 | `format_incident_history` incluye header con display_id |
| 14 | `format_incident_history` muestra evento rejected con ❌ |
| 15 | Permisos: empleado puede ver historial de su propio reporte |
| 16 | Permisos: encargado HK NO puede ver historial de incidencia de mantenimiento |
| 17 | `save_event` se inserta desde `update_incident_state_atomic` — verificar con `get_events` |

---

## Para después (fuera de B.5)

- Política de retención de eventos (borrar eventos de incidencias cerradas hace >6 meses).
- `/eventos` o `/recientes` — lista de últimas N acciones en todo el hotel (vista del gerente).
- Timeline en notificaciones ASIGNADA y EN_PROCESO (hoy solo en CERRADA).
- Filtros temporales en `/historial`.
- Índice en `incident_events(actor_telegram_id)` ya está — podría usarse para "¿qué hizo Carlos hoy?".
- La tabla `notifications` y `incident_events` son redundantes para notification_sent/failed — 
  en B.6+ podríamos limpiar `notifications` y usar solo `incident_events`. No tocar en este sprint.
