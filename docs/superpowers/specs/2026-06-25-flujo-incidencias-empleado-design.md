# Flujo de incidencias simplificado + entrada del empleado

Fecha: 2026-06-25
Estado: aprobado

## Contexto

Durante testing en vivo, el flujo de work-order se sentía "complicado y sin
sentido" del lado del empleado asignado. La investigación reveló dos huecos
reales, no solo percepción:

1. **El empleado no puede ver sus incidencias asignadas.** `permissions.can_see_incident`
   solo deja a un `EMPLEADO` ver las que **él reportó** (`employee_name == user`),
   no las **asignadas** a él. No existe comando de "mis tareas".
2. **La notificación de asignación no trae botones.** `notifier/state_change.py::notify_assignee`
   envía solo texto ("Entrá a tus pendientes…") sin teclado, y "tus pendientes" no
   existe. El empleado se entera de la tarea pero no tiene cómo actuar.

Además, el paso obligatorio "Comenzar" (estado `EN_PROCESO`) agrega fricción: el
modelo mental del usuario es *asignar → empleado termina → gerente valida o reabre*.

## Objetivo

Que el empleado vea lo asignado y actúe con un click, y que "Comenzar" sea
opcional, sin perder la visibilidad "en proceso" para quien la quiera.

## Cambios

### 1. Estado EN_PROCESO opcional — `config/transitions.py`
`terminado` admite origen `ASIGNADA` además de `EN_PROCESO`:
```python
"terminado": [IncidentState.EN_PROCESO, IncidentState.ASIGNADA],
```
Resto de la máquina sin cambios. `transitions.py` sigue siendo única fuente de verdad.

### 2. Botones del ejecutor en ASIGNADA — `notifier/format.py::build_keyboard_for_state`
```
ASIGNADA:  [ ⏳ Lo estoy haciendo ] [ ✅ Lo terminé ]
           [ 🔄 Reasignar ] [ ❌ Cancelar ]
```
EN_PROCESO mantiene "Lo terminé" + Reasignar/Cancelar. Labels más amigables.

### 3. Teclado en la notificación de asignación — `notifier/state_change.py::notify_assignee`
Adjuntar `build_keyboard_for_state(incident_id, IncidentState.ASIGNADA)` al enviar el
aviso, para que el asignado actúe en el mismo mensaje.

### 4. Comando `/mistareas` — hueco #1
- `storage/queries.py`: nueva `get_incidents_assigned_to(telegram_id)` → incidencias
  no terminales con `assigned_to_telegram_id == tid`.
- `handlers/command_handler.py`: `handle_mistareas` que lista cada pendiente con su
  estado y sus botones; registrar en `bot.py` y agregar al `/help`.
- `permissions.can_see_incident`: un EMPLEADO también ve las asignadas a él (hace que
  `/abiertas` también las muestre).

## Flujo resultante
```
Empleado reporta → gerente ASIGNA a Jaime
  → Jaime: [Lo estoy haciendo] (opcional) → [Lo terminé]  → avisa al gerente
  → Gerente: [Validar y cerrar] ó [Reabrir]
```

## Testing
- Transición `terminado` directo desde ASIGNADA.
- `get_incidents_assigned_to` y `can_see_incident` para el asignado.
- `notify_assignee` adjunta teclado (fake sender, patrón `tests/test_notifier.py`).
- E2E en `tests/test_hotel_scenarios.py`: asignar → terminar directo → validar.

## Fuera de alcance
- No se reconstruye la tabla ni se cambian otros estados.
- No se toca el flujo de reportes de turno ni Sheets (las columnas ya mapean bien).
