# Sprint B.3 — Botones de acción en notificaciones

## Decisión: Opción A para actor_telegram_id en callback_data

**Elección**: incluir `actor_telegram_id` directamente en el callback_data.

**Formato**: `incident_action:{incident_id}:{sub_action}:{actor_telegram_id}`
**Ejemplo real**: `incident_action:42:tomar:444444444` → 36 chars, bien por debajo del límite de 64 bytes de Telegram.

**Por qué no Opción B**: guardar el destinatario en SQLite requeriría una tabla adicional o una columna extra en `notifications`, y una consulta adicional en cada callback. Opción A es sin estado, predecible, y cabe perfectamente.

---

## Análisis del código actual

### `storage.py`
- `init_db()` ya tiene el patrón de migración segura: verifica con `PRAGMA table_info` antes de `ALTER TABLE`. Lo replicamos para las 5 columnas nuevas.
- `save()` no necesita cambios: la columna `estado` tendrá `DEFAULT 'ABIERTA'`, así que todos los nuevos INSERTs sin especificar `estado` quedan como ABIERTA.

### `notifier.py`
- `format_notification_message` retorna `str`. Llamada en `notify_incident` línea 132. Necesitamos cambiar a `tuple[str, InlineKeyboardMarkup | None]` y actualizar la llamada.
- `send_notification_with_logging` envía mensaje/foto sin `reply_markup`. Necesita un parámetro `reply_markup=None`.

### `handlers/callback_handler.py`
- `query.answer()` se llama al inicio para TODOS los actions. Problema: para `incident_action:*` necesitamos `query.answer("error", show_alert=True)` en casos de fallo, pero Telegram solo procesa el primer `answer()` por callback query.
- **Solución**: separar el handling de `incident_action:*` ANTES del `query.answer()` del top. El handler de `incident_action` gestiona su propio `answer()`. Los branches de `confirm` y `correct` siguen usando el `query.answer()` del top.

### `permissions.py`
- `can_act_on_incident(user, incident)` ya existe y funciona. No tocar.
- `get_user(telegram_id, employees)` ya existe. No tocar.

---

## Pasos de implementación

### Paso 1 — `storage.py`: migración + 3 funciones

**1a. Migración en `init_db()`** (patrón ya existente):
```python
cls_cols = [row[1] for row in con.execute("PRAGMA table_info(classifications)").fetchall()]
for col, defval in [
    ("estado", "ABIERTA"),
    ("assigned_to_telegram_id", None),
    ("assigned_at", None),
    ("closed_at", None),
    ("resolution_time_minutes", None),
]:
    if col not in cls_cols:
        default = f" DEFAULT '{defval}'" if defval else ""
        con.execute(f"ALTER TABLE classifications ADD COLUMN {col} TEXT{default}")
```

**1b. `get_incident(incident_id)`**: SELECT * FROM classifications WHERE id = ?

**1c. `update_incident_state(incident_id, new_state, actor_telegram_id)`**:
- Leer estado actual
- Validar transición según tabla:

| Estado actual | ASIGNADA | EN_PROCESO | CERRADA |
|---------------|----------|------------|---------|
| ABIERTA       | ✅       | ✅         | ✅      |
| ASIGNADA      | ❌       | ✅         | ✅      |
| EN_PROCESO    | ❌       | ❌         | ✅      |
| CERRADA       | ❌       | ❌         | ❌      |

- Para ASIGNADA: UPDATE con `assigned_to_telegram_id`, `assigned_at=now`
- Para EN_PROCESO: UPDATE estado, y si `assigned_to_telegram_id` es NULL → asignar actor
- Para CERRADA: UPDATE con `closed_at=now`, calcular `resolution_time_minutes` desde `timestamp`
- Devolver `{success: bool, new_state: str, reason: str | None}`

**1d. `get_incident_assignee(incident_id)`**: si tiene `assigned_to_telegram_id`, devuelve dict con ese campo. Si no, None.

**Verificación paso 1**: `python -m pytest tests/test_incident_actions.py -k storage`

---

### Paso 2 — `notifier.py`: keyboard + nuevas funciones

**2a. `build_keyboard_for_state(incident_id, estado, actor_telegram_id)`**:
```python
cb = lambda action: f"incident_action:{incident_id}:{action}:{actor_telegram_id}"
buttons_by_state = {
    "ABIERTA":    [["🙋 Tomar", cb("tomar")], ["⏳ En proceso", cb("proceso")], ["✅ Cerrar", cb("cerrar")]],
    "ASIGNADA":   [["⏳ En proceso", cb("proceso")], ["✅ Cerrar", cb("cerrar")]],
    "EN_PROCESO": [["✅ Cerrar", cb("cerrar")]],
    "CERRADA":    [],  # → return None
}
```
Devuelve `InlineKeyboardMarkup` con una sola fila de botones, o `None` si CERRADA.

**2b. `format_notification_message`** — nueva firma:
```python
def format_notification_message(
    incident: dict,
    reporter: dict,
    incident_id_display: str,
    is_redirect: bool = False,
    actual_recipient_name: str | None = None,
    actual_recipient_telegram_id: int | None = None,
) -> tuple[str, InlineKeyboardMarkup | None]:
```

Cambios en el cuerpo:
- Leer `estado = incident.get("estado", "ABIERTA")`
- Para estado ABIERTA: header `🔔 Nueva incidencia — {id}`
- Para estado ASIGNADA: header `🔔 {id} — ASIGNADA a {assignee_name}`  
- Para estado EN_PROCESO: header `🔔 {id} — EN PROCESO`
- Para estado CERRADA: header `🔔 {id} — ✅ CERRADA`
- Para CERRADA, footer diferente: `Resuelta por: {assignee_name}` + `Tiempo de resolución: X min`
- Para ASIGNADA/EN_PROCESO, añadir `Hace: X min` y `Asignado: hace Y min`
- Llamar `build_keyboard_for_state(incident["id"], estado, actual_recipient_telegram_id)` para el keyboard
- Devolver `(text, keyboard)`

**2c. `send_notification_with_logging`** — añadir `reply_markup=None`:
```python
await bot.send_message(chat_id=..., text=message, reply_markup=reply_markup)
await bot.send_photo(chat_id=..., photo=f, caption=message, reply_markup=reply_markup)
```

**2d. Actualizar `notify_incident`**:
```python
msg, keyboard = format_notification_message(
    incident=incident,
    reporter=reporter_employee,
    incident_id_display=display_id,
    is_redirect=is_redirect,
    actual_recipient_name=recipient_name if is_redirect else None,
    actual_recipient_telegram_id=tid,  # siempre el real, para callback_data
)
await send_notification_with_logging(..., message=msg, reply_markup=keyboard, ...)
```

**2e. `notify_employee_state_change(bot, incident, new_state, actor_name, employees)`**:
- Buscar al empleado que reportó por `incident["employee_name"]`
- Si no tiene `telegram_id` conocido, skip silencioso
- Mensajes según estado:
  - ASIGNADA: `📬 {actor} se está ocupando de tu reporte {id} ({descripcion_corta})...`
  - EN_PROCESO: `📬 {actor} está resolviendo tu reporte {id}.`
  - CERRADA: `📬 ✅ Tu reporte {id} fue resuelto por {actor}. Gracias por reportarlo.`
- Si el empleado está en redirect_mode=admin (su telegram_id coincide con ADMIN_TELEGRAM_ID), mandar también al admin con prefijo `🧪`

**Verificación paso 2**: `python -m pytest tests/test_incident_actions.py -k keyboard`

---

### Paso 3 — `handlers/callback_handler.py`: handler de incident_action

Estructura del handler actualizado:
```python
async def handle_callback(update, context):
    query = update.callback_query
    action = query.data

    # Incident actions manejan su propio query.answer()
    if action.startswith("incident_action:"):
        await _handle_incident_action(query, context)
        return

    await query.answer()  # confirm/correct siguen igual

    if action == "confirm":
        ...  # sin cambios
    elif action == "correct":
        ...  # sin cambios
```

`_handle_incident_action(query, context)`:
1. Parsear `incident_action:{incident_id}:{sub_action}:{actor_id}`
2. Cargar `actor = employees.get(actor_telegram_id)`
3. Cargar `incident = storage.get_incident(incident_id)`
4. Si actor es None o incident es None → `query.answer("Error interno", show_alert=True)`, return
5. Si `not permissions.can_act_on_incident(actor, incident)` → `query.answer("No tenés permisos sobre esta incidencia", show_alert=True)`, return
6. Mapear sub_action → new_state: `{tomar: ASIGNADA, proceso: EN_PROCESO, cerrar: CERRADA}`
7. `result = storage.update_incident_state(incident_id, new_state, actor_telegram_id)`
8. Si `not result["success"]` → `query.answer(result["reason"], show_alert=True)`, return
9. Cargar `updated_incident = storage.get_incident(incident_id)` (con nuevos campos)
10. Obtener nombre del asignado si aplica
11. `msg, keyboard = format_notification_message(updated_incident, reporter, display_id, is_redirect=False)`
12. Editar mensaje: si `query.message.photo` → `edit_message_caption`, si no → `edit_message_text`
13. `await notifier.notify_employee_state_change(context.bot, updated_incident, new_state, actor["nombre"], employees)`
14. `await query.answer()` (dismiss loading)

Nota: el reporter se recupera buscando en `employees` por `incident["employee_name"]` — necesitamos una función helper o buscar linealmente.

**Verificación paso 3**: `python -m pytest tests/test_incident_actions.py`

---

### Paso 4 — Tests en `tests/test_incident_actions.py`

12 tests mínimos (todos sin red, con DB en memoria):

1. Tomar ABIERTA → ASIGNADA, guarda assignee y assigned_at
2. Tomar ASIGNADA → falla con reason "ya está asignada"
3. EN_PROCESO desde ABIERTA → cambia + asigna actor
4. EN_PROCESO desde ASIGNADA → cambia, no toca assignee original
5. Cerrar desde ASIGNADA → CERRADA, closed_at, resolution_time_minutes calculado
6. Cerrar ya CERRADA → falla
7. build_keyboard_for_state ABIERTA → 3 botones
8. build_keyboard_for_state EN_PROCESO → 1 botón
9. build_keyboard_for_state CERRADA → None
10. can_act_on_incident: Carlos Mant puede sobre incidencia de MANTENIMIENTO
11. can_act_on_incident: Laura HK NO puede sobre incidencia de MANTENIMIENTO
12. can_act_on_incident: Alfredo Gerente puede sobre cualquier incidencia

**Cómo testear storage sin bot real**: usar `DB_PATH` de storage apuntando a `:memory:` o a un archivo temporal. Patch `storage.DB_PATH` en el setUp del test.

---

## Para después (fuera de B.3)

- Timer de escalado automático si no se toma en X minutos
- Reasignación entre encargados
- Botones en OBSERVACION/GUEST_INTEL (quizás en B.5)
- `edit_message_caption` para fotos cuando se actualiza estado — actualmente el handler detecta `query.message.photo` y desvía, pero la lógica de reconstrucción de foto es más compleja (la URL de foto no está en `incident`).
- Recuperar el reporter por telegram_id en vez de nombre (actualmente buscamos por nombre, que puede no ser único)

---

## Orden de implementación sugerido

1. `storage.py` → tests de storage pasan
2. `notifier.py` (solo `build_keyboard_for_state`) → tests de keyboard pasan
3. `notifier.py` (resto: `format_notification_message`, `send_notification_with_logging`, `notify_incident`, `notify_employee_state_change`)
4. `handlers/callback_handler.py` → todos los tests pasan
5. Verificar que los tests de sprints anteriores siguen pasando
