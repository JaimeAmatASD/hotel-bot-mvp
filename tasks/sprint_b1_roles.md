# Sprint B.1 — Roles y estructura de permisos

## Observaciones del código actual

- `bot.py:19` — `load_employees()` devuelve `{telegram_id: employee_dict}`. El dict completo del empleado ya se guarda en `bot_data["employees"]`. En cuanto añadamos `rol` al JSON, estará disponible automáticamente. **No hay que tocar `bot.py`.**
- `employees.json` — 4 empleados, sin campo `rol`. El `departamento` de Jaime es `"Spa"` (minúscula) — lo normalizamos a `"SPA"` al actualizar.
- `config/rules.py` — no tiene `CATEGORY_TO_DEPARTMENT`. Hay que añadirlo.
- La compatibilidad hacia atrás (empleados sin `rol`) se maneja en `permissions.py`, no en `bot.py`.

---

## Checkboxes de implementación

### 1. `config/employees.json`
- [ ] Añadir campo `"rol": "EMPLEADO"` a los 4 empleados existentes
- [ ] Normalizar `"Spa"` → `"SPA"` en el empleado de Jaime
- [ ] Añadir los 4 empleados nuevos: Carlos (ENCARGADO MANTENIMIENTO), Laura (ENCARGADO HK), Sofía (ENCARGADO RECEPCION), Alfredo (GERENTE_GENERAL)

### 2. `config/rules.py`
- [ ] Añadir `CATEGORY_TO_DEPARTMENT` con el mapeo especificado

### 3. `permissions.py` (nuevo en raíz)
- [ ] Definir `Role = Literal["EMPLEADO", "ENCARGADO", "GERENTE_GENERAL"]`
- [ ] Implementar `get_user(telegram_id, employees) -> dict | None`
- [ ] Implementar `get_role(telegram_id, employees) -> Role | None` — con default `"EMPLEADO"` si no tiene campo `rol`
- [ ] Implementar `get_department(telegram_id, employees) -> str | None`
- [ ] Implementar `is_manager(telegram_id, employees) -> bool`
- [ ] Implementar `can_act_on_incident(user, incident) -> bool`
- [ ] Implementar `can_see_incident(user, incident) -> bool`
- [ ] Implementar `get_notification_recipients(incident, employees) -> list[int]` — usa `CATEGORY_TO_DEPARTMENT` de rules.py
- [ ] Implementar `filter_visible_incidents(user, incidents) -> list[dict]`

### 4. `bot.py`
- [ ] Verificar que no necesita cambios (confirmado: ya guarda el dict completo)

### 5. `tests/test_permissions.py` (nuevo)
- [ ] Test 1: `get_role` → EMPLEADO correcto
- [ ] Test 2: `get_role` → ENCARGADO correcto
- [ ] Test 3: `get_role` → GERENTE_GENERAL correcto
- [ ] Test 4: `get_role` → None para telegram_id no registrado
- [ ] Test 5: `get_role` → "EMPLEADO" por defecto si no tiene campo `rol` (backward compat)
- [ ] Test 6: `is_manager` → True para ENCARGADO, True para GERENTE_GENERAL, False para EMPLEADO
- [ ] Test 7: `can_act_on_incident` → ENCARGADO puede actuar sobre incidencia de SU departamento
- [ ] Test 8: `can_act_on_incident` → ENCARGADO NO puede actuar sobre incidencia de otro departamento
- [ ] Test 9: `can_act_on_incident` → GERENTE_GENERAL puede actuar sobre cualquier incidencia
- [ ] Test 10: `can_see_incident` → ENCARGADO ve incidencias de su departamento
- [ ] Test 11: `get_notification_recipients` → MANTENIMIENTO devuelve encargado de mant + gerente
- [ ] Test 12: `get_notification_recipients` → categoría sin encargado devuelve solo gerente
- [ ] Test 13: `filter_visible_incidents` → filtra lista mixta para un encargado correctamente
- [ ] Test bonus: `employees.json` parsea sin errores con la nueva estructura

### 6. `tasks/lessons.md`
- [ ] Añadir entrada sobre estructura de roles (3 niveles, mapeo categoría→departamento)
- [ ] Añadir entrada sobre por qué `permissions.py` es módulo aparte
- [ ] Añadir entrada sobre compatibilidad hacia atrás con `rol` ausente

---

## Notas de diseño

**¿Por qué backward compat en `permissions.py` y no en `bot.py`?**  
El único punto de verdad sobre roles es `permissions.py`. Si la carga en `bot.py` normalizara el `rol`, estaríamos mezclando responsabilidades. Las funciones de `permissions.py` ya reciben el dict crudo del empleado — es el lugar natural para hacer `.get("rol", "EMPLEADO")`.

**`can_act_on_incident` necesita saber el departamento de la incidencia.**  
La incidencia tiene campo `categoria`. Usamos `CATEGORY_TO_DEPARTMENT` para traducir categoría → departamento, y comparamos con el departamento del encargado.

**`get_notification_recipients` — ¿qué estructura tiene `incident`?**  
Las incidencias guardadas en SQLite tienen `categoria`. El mapeo `CATEGORY_TO_DEPARTMENT` convierte eso a departamento para saber qué encargado notificar.

---

## Para después (no implementar en B.1)

- Filtros configurables del gerente general (B.2)
- Notificaciones reales por Telegram (B.2)
- Integración de `permissions.py` en handlers (B.2-B.4)
- Comandos `/abiertas`, `/hab N` con permisos (B.4)

---

## Criterio de éxito

1. `pytest tests/test_permissions.py` pasa los 13+ tests
2. Bot sigue respondiendo igual para empleados (test manual)
3. `permissions.py` existe con todas las funciones
