# Diseño: Ciclo de vida de incidencias como work-order

**Fecha:** 2026-06-17
**Estado:** Aprobado (diseño) — pendiente plan de implementación
**Origen:** Necesidad de delegación ("el encargado quiere pasar una incidencia a otra persona"), que al analizarla reveló que el modelo de estados actual mezcla responsabilidades. Se rediseña el ciclo de vida completo siguiendo la lógica estándar de un sistema de órdenes de trabajo (work orders).

## Problema

Hoy el flujo es `ABIERTA → ASIGNADA → EN_PROCESO → CERRADA` y el botón **Tomar** mezcla dos acciones distintas:

1. Reconocer que la incidencia existe / hacerse responsable.
2. Asignarla a una persona.

Consecuencias:

- Un encargado solo puede quedarse la incidencia él mismo; **no existe delegación** a otra persona del equipo.
- No se distingue entre "el técnico dice que terminó" y "el supervisor valida y cierra", lo que elimina trazabilidad y permite discusiones posteriores.
- Los empleados no pueden actuar sobre ninguna incidencia (`can_act_on_incident` devuelve `False` para `EMPLEADO`), por lo que aunque se les asignara una tarea no podrían moverla.

## Objetivo

Convertir el ciclo de vida en un work-order profesional pero adecuado a un hotel boutique (20-50 habitaciones): separar **reportar / asignar / resolver / validar-cerrar** como acciones distintas, con trazabilidad de quién hizo cada una, sin caer en la complejidad de un PMS grande.

## No-objetivos (YAGNI)

- No se agrega el estado intermedio `REVISADA` ("el gerente la vio pero no la asignó"): agrega fricción sin valor para un hotel pequeño. `NUEVA` pasa directo a `ASIGNADA`.
- No se implementa auto-cierre por tiempo. La validación es siempre manual (decisión del usuario: doble paso con validación real).
- No se toca la clasificación por IA, la transcripción ni el sync a Sheets más allá de las columnas nuevas.

## Estados (nuevo `IncidentState`)

```
NUEVA → ASIGNADA → EN_PROCESO → RESUELTA → CERRADA
   │        │           │           │
   └────────┴───────────┴───────────┴──────→ CANCELADA
```

- **NUEVA** — recién reportada, sin asignar. (Reemplaza a `ABIERTA`.)
- **ASIGNADA** — tiene un responsable concreto.
- **EN_PROCESO** — el responsable empezó a trabajar.
- **RESUELTA** — el responsable declara "terminé". Pendiente de validación. **No** es terminal.
- **CERRADA** — un manager validó y cerró. Terminal.
- **CANCELADA** — incidencia errónea/duplicada/descartada. Terminal. Alcanzable desde cualquier estado no terminal.

## Transiciones y permisos

| Desde | Acción (botón) | Hacia | Quién puede |
|-------|----------------|-------|-------------|
| NUEVA | 👤 Asignar | ASIGNADA | Encargado (su depto) / Gerente (cualquier depto) |
| NUEVA | 🙋 Tomar (para mí) | ASIGNADA | Encargado / Gerente |
| ASIGNADA | ⏳ Comenzar | EN_PROCESO | **El asignado** o un manager |
| EN_PROCESO | ✅ Trabajo terminado | RESUELTA | **El asignado** o un manager |
| RESUELTA | ✅ Validar y cerrar | CERRADA | Manager |
| RESUELTA | ↩ Reabrir | ASIGNADA | Manager |
| ASIGNADA / EN_PROCESO | 🔄 Reasignar | ASIGNADA (otro responsable) | Manager |
| cualquier estado no terminal | ❌ Cancelar | CANCELADA | Manager |

"Manager" = `ENCARGADO` (limitado a su departamento) o `GERENTE_GENERAL` (sin límite).

### Cambio clave en el modelo de permisos

Regla nueva en `permissions.can_act_on_incident` (o función acompañante):

> Un `EMPLEADO` puede ejecutar las acciones de **ejecutor** (Comenzar, Trabajo terminado) **si y solo si** la incidencia está asignada a él (`assigned_to_telegram_id == user.telegram_id`).
> Las acciones de **gestión** (Asignar, Tomar, Validar/Cerrar, Reabrir, Reasignar, Cancelar) siguen requiriendo rol manager.

Esto permite que el asignado mueva *su* tarea sin poder tocar las de los demás.

## Mecánica de asignación

Al pulsar **👤 Asignar**:

- **Encargado:** el bot muestra botones con la gente del departamento del incidente (la categoría ya determina el depto vía `CATEGORY_TO_DEPARTMENT`), más "🙋 Para mí". El encargado toca un nombre.
- **Gerente general:** primero elige departamento (menú de deptos), luego la persona. Puede asignar a cualquier departamento, no solo al del incidente.

Sin texto libre: evita errores de tipeo y nombres ambiguos.

## Notificaciones

- **NUEVA** → managers del depto + gerente general (comportamiento actual, vía `get_notification_recipients`).
- **ASIGNADA** → aviso al asignado: "Nueva tarea: …".
- **RESUELTA** → aviso a los managers: "X marcó resuelto el #N, validá".
- **CERRADA** → aviso al empleado que **reportó**: "Tu reporte fue resuelto".
- **CANCELADA** → aviso al asignado (si había uno).

Todas en paralelo con `asyncio.gather(..., return_exceptions=True)` como hoy.

## Trazabilidad (datos)

Campos a agregar/usar en `classifications` para separar los 4 actores (reportó / asignó / resolvió / validó):

| Campo | Estado | Nota |
|-------|--------|------|
| `employee_*` (reportó) | ya existe | quién reportó |
| `assigned_to_telegram_id`, `assigned_at` | ya existen | a quién |
| `assigned_by` | **nuevo** | qué manager asignó |
| `resolved_by`, `resolved_at` | **nuevos** | quién declaró resuelto |
| `closed_by` | **nuevo** | quién validó/cerró (`closed_at` ya existe) |
| `cancelled_by`, `cancel_reason` | **nuevos** | `cancel_reason` opcional |

Google Sheets (pestaña Incidencias): agregar columnas **Asignado por · Resuelto por · Validado por**.

## Callbacks (respetan el invariante de 3 partes)

El proyecto exige callbacks de exactamente 3 partes. Se mantiene:

- Transiciones simples: `incident_action:{id}:{accion}` — `accion ∈ {tomar, comenzar, terminado, validar, reabrir, cancelar}`.
- Selección de persona: `assign_to:{id}:{telegram_id}`.
- Menú de departamento (solo gerente): `assign_dept:{id}:{depto}`.

El actor SIEMPRE sale de `query.from_user.id`, nunca del callback.

## Migración

- Renombrar el valor de enum `ABIERTA` → `NUEVA` y migrar las filas existentes en `classifications` (`UPDATE ... SET estado='NUEVA' WHERE estado='ABIERTA'`).
- Agregar las columnas nuevas (`assigned_by`, `resolved_by`, `resolved_at`, `closed_by`, `cancelled_by`, `cancel_reason`) con `ALTER TABLE` idempotente.
- Implementar dentro del hook `storage/migrations.apply_pending` (ya cableado en `bot.py`).
- `update_incident_state_atomic` en `storage/events.py` sigue siendo la **única** función de transición de estado; se extiende para los nuevos estados/acciones.

## Componentes afectados

| Componente | Cambio |
|------------|--------|
| `config/enums.py` | Nuevos estados `NUEVA`, `RESUELTA`, `CANCELADA`; quitar/renombrar `ABIERTA` |
| `permissions.py` | Regla "asignado puede ejecutar"; targets de asignación por rol |
| `storage/events.py` | `update_incident_state_atomic` con nuevas transiciones + campos de trazabilidad |
| `storage/schema.py` + `storage/migrations.py` | Columnas nuevas + migración de `ABIERTA` |
| `notifier/format.py` | Teclados por estado con los botones nuevos |
| `notifier/` (dispatch/filters) | Notificaciones a asignado / reporter / managers según transición |
| `handlers/callback_handler.py` | Manejo de `assign_to`, `assign_dept` y nuevas acciones |
| `presenters/` (constants, format_incidents, format_history) | Etiquetas/íconos de los nuevos estados y acciones |
| `sheets_sync.py` | Columnas nuevas en Incidencias |

## Testing (requisito explícito del usuario: "lo testeamos fuerte")

- **Unit — máquina de estados:** cada transición válida y cada transición inválida rechazada, por estado de origen.
- **Unit — permisos:** asignado puede Comenzar/Terminar su tarea; no puede las de otros; empleado no asignado no puede nada; encargado limitado a su depto; gerente cross-depto.
- **Unit — asignación:** targets correctos por rol; `assign_to`/`assign_dept` generan estado y trazabilidad correctos.
- **Unit — atomicidad / idempotencia:** doble click en un botón no duplica transición (ya cubierto por `action_rejected_already_done`); extender a los nuevos estados.
- **Unit — Sheets:** filas con las columnas nuevas.
- **E2E (estilo `tests/test_hotel_scenarios.py`, fakes):** flujo completo reportar → asignar a otro → comenzar → resuelto → validar/cerrar; rechazo de empleado no asignado; reabrir; reasignar; cancelar; notificaciones a cada destinatario.
- La suite normal (`venv/bin/pytest -q`) debe quedar verde.

## Decisiones registradas

- Doble paso con validación real (RESUELTA distinta de CERRADA). *(usuario)*
- Asignación por botones; gerente cross-departamento, encargado solo su depto. *(usuario)*
- Reabrir vuelve a ASIGNADA (no a EN_PROCESO).
- Notificar al reporter al cerrar.
- Renombrar `ABIERTA` → `NUEVA` con migración.
