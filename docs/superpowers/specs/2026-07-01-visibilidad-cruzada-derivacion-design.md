# Visibilidad cruzada + derivación entre departamentos

Fecha: 2026-07-01
Estado: aprobado

## Contexto

Hoy el departamento responsable de una incidencia se deduce **solo** de la
`categoria` que asigna la IA (`permissions._incident_department` →
`CATEGORY_TO_DEPARTMENT`). De ahí:

- `get_notification_recipients` avisa al **encargado del depto de contenido** +
  **gerente general**. El encargado del depto del **reportante** no se entera de
  nada, aunque el reporte haya salido de su equipo.
- No existe forma de **derivar** una incidencia a otro depto cuando la
  clasificación no corresponde o el tema es de otro sector.

El usuario quiere: (a) que el encargado del depto del reportante reciba una
**copia informativa** (sin poder de edición) de lo que reporta su gente, y (b)
que los encargados puedan **derivar** temas a otros deptos, transfiriendo la
propiedad.

## Decisiones (del brainstorming)

- **Alcance**: solo `INCIDENCIA` (OBSERVACION/GUEST_INTEL siguen sin notificar).
- **CC**: el encargado del depto del reportante (`employee_dept`) y el del depto
  original (`categoria`) reciben copia de **solo lectura**, con una única acción
  disponible: **derivar**. No pueden asignar/cerrar.
- **CC en cadena (A→B→C)**: el CC se calcula **de la fila sola** = reportante +
  depto original. Los saltos intermedios no quedan CC individualmente (YAGNI; se
  evita escanear el historial en cada chequeo).
- **Derivar transfiere la propiedad**: el encargado del nuevo depto pasa a ser el
  dueño; el anterior queda como CC de solo lectura. Trazable (de→a, por quién).
- **Reset al derivar**: la incidencia vuelve a `NUEVA` y se limpia el asignado,
  para que el nuevo depto la asigne de cero. Solo se puede derivar desde estados
  **no terminales** (NUEVA/ASIGNADA/EN_PROCESO).

## Modelo de datos

Nueva columna `departamento_responsable TEXT` en `classifications` (nullable).
Migración v2 (`ALTER TABLE ... ADD COLUMN`), append a `MIGRATIONS` en
`storage/migrations.py`.

- `null` = usar el mapeo de `categoria` → **sin backfill**; las filas existentes
  se comportan igual que hoy.
- Derivar la setea explícitamente al depto destino.

## Cambios

### 1. `permissions.py` — depto responsable, propiedad, CC, permiso de derivar

- `_incident_department(incident)`: devolver `incident["departamento_responsable"]`
  si está seteado; si no, el mapeo actual de `categoria`. (Es el único punto que
  ya consumen `can_act_on_incident`, `can_see_incident`, `get_notification_recipients`,
  así que dueño/permisos siguen automáticamente al depto responsable.)

- `_cc_departments(incident) -> set[str]`: `{employee_dept, categoria→dept}` menos
  el depto responsable actual. Función pura, calculada de la fila.

- `can_see_incident` (encargado): ve si su depto ∈ `{responsable} ∪ _cc_departments`.
  (Gerente general y reglas de empleado sin cambios.)

- `can_do_action`: caso especial para `derivar` **antes** de los checks de
  management/execution:
  `if action == "derivar": return is_manager(user) and can_see_incident(user, incident) and estado no terminal`.
  El resto de acciones de management siguen exigiendo dueño (`can_act_on_incident`),
  así que el CC **no** puede asignar/cerrar.

### 2. `config/transitions.py` — registrar `derivar`

`derivar` **no** es una transición del ciclo de vida (no está en `ACTION_TO_STATE`
ni `EXPECTED_FROM`); es ortogonal y su efecto de estado (reset a NUEVA) lo aplica
la función de storage. Se documenta como acción de gestión de alcance ampliado y
se lista aparte de `MANAGEMENT_ACTIONS` para no heredar el check de dueño. Verbo
nuevo: `derivar`.

### 3. `storage/events.py` — `derive_incident`

Nueva función (hermana de `update_incident_state_atomic`, no la reutiliza porque
derivar no es una transición estándar):

```
derive_incident(incident_id, target_dept, *, actor_telegram_id, actor_name, actor_role) -> dict
```

- Set `departamento_responsable = target_dept`, `estado = NUEVA`,
  `assigned_to_telegram_id/assigned_at/assigned_by = NULL`.
- Escribe `incident_events` con `action="derivar"`, `from_state`/`to_state` reflejando
  el reset, y `extra = {"from_dept": ..., "to_dept": target_dept}`.
- Devuelve la incidencia actualizada.

### 4. `notifier/` — ruteo y teclado por destinatario

- `permissions.get_notification_recipients`: además del dueño (encargado del depto
  responsable) y el gerente general (gateado por prefs, como hoy), incluir al
  encargado de cada depto en `_cc_departments`. Devolver info suficiente para que
  el dispatch sepa si cada destinatario es **dueño** o **CC** (ej. lista de
  `(tid, is_owner)` en vez de solo `tid`).
- `dispatch._notify_one_recipient` / `format.format_notification_message`: si el
  destinatario es CC, el teclado trae **solo** el botón "Derivar"; si es dueño, el
  teclado completo actual.
- Al derivar (callback), notificar al **nuevo dueño** con el teclado completo.

### 5. `handlers/callback_handler.py` + `presenters/keyboards.py` — flujo de derivar

- Botón "Derivar" → `incident_action:{id}:derivar` abre un teclado de selección de
  depto destino (reutilizar el patrón del teclado de asignar depto; excluir el
  depto responsable actual).
- Callback nuevo `derive_dept:{id}:{depto}` (3 partes, actor de `query.from_user.id`):
  valida `can_do_action(user, incident, "derivar")`, llama `storage.derive_incident`,
  confirma al que derivó y dispara la notificación al nuevo dueño.

## Testing

- **Unit permisos**: `_incident_department` respeta el override; `_cc_departments`
  correcto; `can_see_incident` incluye reportante + original; `can_do_action`
  permite `derivar` al CC pero le niega `asignar`/`validar`; `derivar` bloqueado en
  estados terminales.
- **Unit storage**: `derive_incident` cambia depto, resetea a NUEVA, limpia
  asignado y escribe el evento con `extra` de→a.
- **Unit notifier**: `get_notification_recipients` incluye al encargado del depto
  del reportante marcado como CC cuando difiere del responsable; el dueño recibe
  teclado completo y el CC solo "Derivar".
- **E2E (`tests/test_hotel_scenarios.py`)**: Jaime (mant) reporta tema de House →
  notifican a House (dueño, teclado completo), Mant (CC, solo derivar) y gerente →
  Mant deriva a Recepción → Recepción pasa a dueño, incidencia vuelve a NUEVA,
  House+Mant quedan CC, evento `derivar` trazable en el historial.

## Fuera de alcance (v1)

- CC individual de cada salto en cadenas de varias derivaciones (solo reportante +
  original).
- Derivación/CC para OBSERVACION y GUEST_INTEL.
- Notificar al reportante (empleado) de la derivación.
- Derivar incidencias en estado terminal (primero reabrir).
