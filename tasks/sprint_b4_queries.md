# Sprint B.4 — Comandos de consulta

## Análisis del código actual

### `handlers/__init__.py`
- `PRIORIDAD_EMOJI` existe ✅ — reusar en lugar de redefinir.
- `_time_ago` en `notifier.py` solo devuelve minutos — no sirve para B.4 (necesitamos horas y días).
- Añadir `format_relative_time` a `handlers/__init__.py` con la versión completa. No modificar `notifier.py`.

### `permissions.py`
- `filter_visible_incidents(user, incidents)` existe ✅ — lo usamos en todos los handlers de query.
- `_incident_department(incident)` existe ✅ — la usamos para filtrar por departamento.
- Falta `can_query_department(user, departamento)` — la añadimos.

### `storage.py`
- Las queries de incidencias usan `categoria`, no `departamento`. El mapeo vive en `permissions._incident_department()`. Consecuencia: el filtrado por departamento se hace **en Python** (fetch all + filter) para aprovechar el código existente. El dataset es pequeño.
- Solo el filtro de `prioridad` irá en SQL (columna directa). El filtro de `estado` también.

### `bot.py`
- El unknown_command handler debe registrarse DESPUÉS de todos los demás para que no intercepte comandos reales. Es un `MessageHandler(filters.COMMAND, ...)`.

### Parsing de argumentos en `/abiertas`
- Args pueden venir en cualquier orden: `/abiertas alta mantenimiento` o `/abiertas mantenimiento alta`.
- Detección: si arg.upper() ∈ {"CRITICA", "ALTA", "MEDIA", "BAJA"} → prioridad; resto → departamento.
- Departamento se normaliza a mayúsculas y se compara con `_incident_department()` sobre cada incidencia.

---

## Pasos de implementación

### Paso 1 — `permissions.py`: `can_query_department`

```python
def can_query_department(user: dict, departamento: str) -> bool:
    """True si el usuario puede filtrar por ese departamento."""
    rol = user.get("rol", "EMPLEADO")
    if rol == "GERENTE_GENERAL":
        return True
    if rol == "ENCARGADO":
        return user.get("departamento", "").upper() == departamento.upper()
    return False
```

**Verificación**: tests de permisos.

---

### Paso 2 — `handlers/__init__.py`: helpers de formateo

**2a. `format_relative_time(timestamp_iso)`**:
```
< 1 min → "ahora mismo"
1-59 min → "hace X min"
1-23 h   → "hace X h"
1+ días  → "hace X días" / "hace 1 día"
```

**2b. `format_priority_emoji(prioridad)`** — ya existe como `PRIORIDAD_EMOJI.get(prioridad, "")`. Wrapper simple para evitar repetición en los formateadores.

**2c. `format_incident_line(incident, employees)`**:
```
🟠 INC-142 — ALTA — Habitación 305 — Goteo en baño
   Mantenimiento · hace 30 min · EN_PROCESO (Carlos)
```
Recibe `employees: dict` para resolver nombre del asignado desde `assigned_to_telegram_id`.

**2d. `format_incident_list(incidents, employees)`**:
Llama a `format_incident_line` por cada uno, añade header con count, footer con hint de `/hab N`.
Límite de 10 visibles; si hay más añade "... y N más. Filtrá por departamento o prioridad."

**2e. `format_room_view(room, incidents_open, incidents_closed, guest_intel, observations, employees)`**:
Construye el texto completo de `/hab N`. Cada sección separada.

**2f. `get_help_text(role, department=None)`**:
Devuelve string con markdown según rol. Tres variantes.

**Verificación**: tests de formateo.

---

### Paso 3 — `storage.py`: 5 funciones de query

**3a. `get_open_incidents(prioridad=None, limit=100)`**:
```sql
SELECT * FROM classifications
WHERE tipo = 'INCIDENCIA'
  AND (estado IS NULL OR estado IN ('ABIERTA', 'ASIGNADA', 'EN_PROCESO'))
  [AND prioridad = ?]
ORDER BY CASE prioridad
    WHEN 'CRITICA' THEN 1 WHEN 'ALTA' THEN 2
    WHEN 'MEDIA' THEN 3 WHEN 'BAJA' THEN 4 ELSE 5
END ASC, timestamp ASC
LIMIT ?
```

Nota: `estado IS NULL` cubre incidencias registradas antes de la migración de B.3.

**3b. `get_incidents_for_room(room_or_zone, days_back=30)`**:
```sql
WHERE tipo = 'INCIDENCIA'
  AND LOWER(ubicacion) LIKE LOWER('%' || ? || '%')
  AND timestamp >= ?
ORDER BY timestamp DESC
```

**3c. `get_guest_intel_for_room(room, days_back=30)`**:
Igual que 3b pero `tipo = 'GUEST_INTEL'`.

**3d. `get_observations_for_room(room_or_zone, days_back=30)`**:
Igual pero `tipo = 'OBSERVACION'`.

**3e. `search_classifications(query, days_back=90, limit=10)`**:
```sql
WHERE timestamp >= ?
  AND (LOWER(message) LIKE LOWER('%' || ? || '%')
    OR LOWER(descripcion) LIKE LOWER('%' || ? || '%')
    OR LOWER(ubicacion) LIKE LOWER('%' || ? || '%'))
ORDER BY timestamp DESC
LIMIT ?
```

**Verificación**: tests de storage.

---

### Paso 4 — `handlers/command_handler.py`: 4 handlers

**`handle_abiertas(update, context)`**:
1. Parsear args: separar en prioridad (si coincide con set conocido) y departamento (resto).
2. Si departamento especificado y `not can_query_department(user, departamento)` → "no tenés acceso a ese departamento".
3. `incidents = storage.get_open_incidents(prioridad=prioridad)` (filtro SQL por prioridad).
4. `visible = permissions.filter_visible_incidents(user, incidents)` (filtro por rol).
5. Si departamento → `visible = [i for i in visible if _dept(i).upper() == departamento.upper()]`.
6. Formatear y responder. Si vacío → "✅ No hay incidencias abiertas."

**`handle_hab(update, context)`**:
1. Si no args → "Usá `/hab 305` o `/hab lobby`".
2. `room = " ".join(args)`.
3. Llamar las 3 funciones de storage.
4. Filtrar open+closed con `filter_visible_incidents`, filtrar guest_intel con rol.
5. Si todo vacío → "sin actividad registrada".
6. Formatear con `format_room_view`.

**`handle_buscar(update, context)`**:
1. `query = " ".join(args)`.
2. Si `len(query) < 3` → "Necesito al menos 3 letras".
3. `results = storage.search_classifications(query)`.
4. `visible = permissions.filter_visible_incidents(user, results)`.
5. Formatear. Si vacío → "🔍 No encontré nada con '{query}'."

**`handle_help(update, context)`**:
1. Obtener role y department del usuario.
2. `await update.message.reply_text(get_help_text(role, department))`.

**Patrones compartidos**: cada handler empieza con:
```python
tid = update.effective_user.id
employees = context.bot_data["employees"]
user = employees.get(tid)
role = user.get("rol", "EMPLEADO") if user else "EMPLEADO"
```

**Verificación**: tests de handlers (mockeando storage).

---

### Paso 5 — `bot.py`: registrar handlers

```python
from handlers.command_handler import handle_debug, handle_notificaciones, \
    handle_abiertas, handle_hab, handle_buscar, handle_help

# ...
app.add_handler(CommandHandler("abiertas", handle_abiertas))
app.add_handler(CommandHandler("hab", handle_hab))
app.add_handler(CommandHandler("buscar", handle_buscar))
app.add_handler(CommandHandler("help", handle_help))

# Unknown command handler — SIEMPRE AL FINAL
async def unknown_command(update, context):
    await update.message.reply_text(
        "❓ Ese comando no existe. Mandá /help para ver los disponibles."
    )
app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
```

---

## Tests en `tests/test_query_commands.py`

15 tests mínimos, sin red, con DB temporal:

| # | Test | Módulo |
|---|------|--------|
| 1 | `get_open_incidents` devuelve solo ABIERTA/ASIGNADA/EN_PROCESO | storage |
| 2 | Ordenado por prioridad CRITICA > ALTA > MEDIA > BAJA | storage |
| 3 | Filtro por prioridad funciona | storage |
| 4 | Incidencias cerradas no aparecen en get_open_incidents | storage |
| 5 | `get_incidents_for_room("305")` encuentra exacto | storage |
| 6 | `get_incidents_for_room("lobby")` case-insensitive | storage |
| 7 | `search_classifications` busca en message Y en descripcion Y en ubicacion | storage |
| 8 | `format_relative_time` devuelve "ahora mismo" para timestamps recientes | handlers |
| 9 | `format_relative_time` devuelve horas para timestamps de >1h | handlers |
| 10 | `format_relative_time` devuelve días para timestamps de >24h | handlers |
| 11 | `format_priority_emoji` devuelve 🔴 para CRITICA | handlers |
| 12 | `get_help_text` EMPLEADO no incluye /notificaciones | handlers |
| 13 | `get_help_text` GERENTE_GENERAL incluye /notificaciones | handlers |
| 14 | Encargado de MANTENIMIENTO no puede query_department HOUSEKEEPING | permissions |
| 15 | Empleado no puede query_department ningún depto | permissions |

Nota: tests de handlers de comando (handle_abiertas, etc.) requieren mocking de bot y storage — incluir al menos 2 tests de integración light con mocks.

---

## Para después (fuera de B.4)

- `/abiertas hoy`, `/abiertas semana` — filtros temporales.
- Paginación en resultados (>10 incidencias con botón "ver más").
- `/hab N` para fotos adjuntas — mostrar thumbnail si la incidencia tenía foto.
- Registrar las queries en una tabla `audit_log` (B.5 lo puede aprovechar).
- `format_incident_line` podría usar `parse_mode="HTML"` para negritas — por ahora texto plano para no complicar el escape de caracteres especiales.
