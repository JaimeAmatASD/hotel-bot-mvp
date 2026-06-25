# Informe de turno acumulativo (fricción cero)

Fecha: 2026-06-25
Estado: aprobado

## Contexto

El `/reporte` actual falla en algo fundamental para el usuario: promete un modelo
"abrir reporte → ir sumando → cerrar" (así lo dice el `/help` y el CLAUDE.md) pero
en realidad es una consolidación retrospectiva, y `/fin` es idéntico a `/reporte`
(`handlers/command_handler.py:343`). El usuario quiere armar el informe **de a
pedazos a lo largo del turno, con fricción cero**, y al final del día obtener un
**informe consolidado con formato de plantilla**. Hoy no hay un modo cómodo para eso,
y la narrativa de turno se pierde (cae en `NO_REPORTE`).

Hallazgo clave: la acumulación automática **ya casi existe**.
`storage.get_classifications_for_employee_recent` junta todo lo no-`NO_REPORTE`/`ERROR`
del empleado que aún no esté en un reporte (`report_id IS NULL`). El trabajo real es
(a) capturar la narrativa de turno, (b) producir la plantilla, (c) arreglar la
incoherencia de comandos, (d) distribuir mejor.

## Decisiones (del brainstorming)

- **Captura**: todo lo del turno se acumula solo, sin sesiones (sin abrir/cerrar).
- **Alcance**: incidencias + notas de huésped + observaciones + **notas narrativas
  del turno** (estas últimas mapeadas a `OBSERVACION`, sin tipo nuevo).
- **Plantilla**: aprobada (ver abajo), con bloque "Queda pendiente" para handover.
- **Distribución**: encargado del depto del autor + gerente general.

## Cambios

### 1. Capturar narrativa de turno como OBSERVACION — `classifier.py`
Afinar el prompt para que registros operativos de turno ("revisé pisos 2-4 sin
novedades", "falta stock de lámparas en depósito") se clasifiquen como `OBSERVACION`
en vez de `NO_REPORTE`. El chit-chat puro (saludos, gossip) sigue en `NO_REPORTE`.
No se crea tipo nuevo ni columnas nuevas.

### 2. Plantilla del informe — `report_processor.py`
Reemplazar el formato actual por la plantilla aprobada. Una sola función de formato
reutilizada por el resumen previo a confirmar, por la notificación al manager y por
`/reporte REP-N` (hoy hay dos formatos distintos).

```
📋 INFORME DE TURNO — REP-014
👤 Jaime A · MANTENIMIENTO
🕐 25/06 · 08:00–16:00 · 7 ítems
──────────────────────────
🔧 INCIDENCIAS (3)
 1. Hab 47 — Ventilador roto · ALTA · ✅ CERRADA
 2. Lobby — Luz parpadeando · MEDIA · 🔧 EN PROCESO
 3. Hab 210 — Canilla goteando · BAJA · 🆕 NUEVA
👤 NOTAS DE HUÉSPED (1)
 4. Hab 305 — Huésped pidió almohadas extra
📝 NOVEDADES DEL TURNO (2)   ← items OBSERVACION
 5. Revisé pisos 2 al 4, sin novedades
 6. Falta stock de lámparas LED en depósito
⏳ QUEDA PENDIENTE PARA EL PRÓXIMO TURNO
 • Lobby — Luz parpadeando (EN PROCESO)
 • Hab 210 — Canilla goteando (NUEVA)
──────────────────────────
Cerrado 16:02 · /reporte REP-014 para ver
```

- **Cabecera**: display_id, autor, depto, fecha, rango horario (primer→último ítem),
  total de ítems.
- **Secciones**: incidencias (con estado+emoji), notas de huésped, novedades
  (OBSERVACION). Secciones vacías se omiten.
- **Queda pendiente**: auto-calculado = incidencias del informe con estado ∉
  {CERRADA, CANCELADA}. Se omite si no hay.

### 3. Comandos — `handlers/command_handler.py`, `presenters/help_text.py`
- `/reporte` (sin args): compila lo capturado desde el último informe (items con
  `report_id IS NULL`), default acotado a 24h. Muestra la plantilla con
  `[✅ Confirmar y cerrar] [✏️ Corregir]`.
- `/fin`: alias explícito de `/reporte` sin args. Corregir el `/help` y CLAUDE.md
  para que describan el modelo real (acumulativo automático + compilar), no
  "abrir/cerrar" sesión.
- `/reporte 6h|24h`: override de ventana (ya existe).
- `/reporte REP-N`: ver uno cerrado **con la misma plantilla** (hoy usa otro formato).

### 4. Distribución — `report_processor.py::notify_manager_report`
Al cerrar, enviar a:
- el **encargado del departamento del autor** → recibe siempre el informe de su
  equipo (no gateado por `NotificationMode`).
- el **gerente general** → sigue gateado por su `NotificationMode == TODO` (como hoy).

Si el autor es él mismo encargado o gerente, no se autonotifica. Respeta
`NOTIFICATION_REDIRECT_MODE`/`ADMIN_TELEGRAM_ID`.

## Testing
- Clasificación: narrativa de turno → OBSERVACION (no NO_REPORTE); chit-chat → NO_REPORTE.
- `consolidate_recent_classifications` junta lo no-reportado y excluye lo ya en un REP.
- Plantilla: secciones presentes/omitidas, estados con emoji, bloque "queda pendiente"
  solo con incidencias abiertas, cabecera con rango horario y totales.
- `/reporte REP-N` usa la plantilla.
- `notify_manager_report` avisa al encargado del depto + gerente.
- E2E (`tests/test_hotel_scenarios.py`): capturar incidencia + nota huésped +
  observación a lo largo del "turno" → `/reporte` → confirmar → REP creado, ítems
  linkeados, informe formateado, aviso a encargado y gerente, y la incidencia abierta
  aparece en "queda pendiente".

## Fuera de alcance (v1)
- Informe agregado de todo un equipo compilado por el gerente (esto es por-persona).
- Tipo de dato nuevo "nota de turno" (se reutiliza OBSERVACION).
- Sesiones explícitas con estado abierto/cerrado.
