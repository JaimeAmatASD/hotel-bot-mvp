# Reportes intra-sector (piloto)

Fecha: 2026-07-01
Estado: aprobado

## Contexto

El bot va a desplegarse como **piloto en un solo sector** (housekeeping o
mantenimiento) antes de escalar. El organigrama es:

```
empleado → encargado de sector → gerente general → dueños
```

En el piloto, el bot cubre la capa operativa **empleado ↔ encargado de sector**.
La visibilidad hacia arriba (gerente general + dueños) se delega a **Google
Sheets** y sus permisos nativos de la hoja, en vez de construir features de
gerente en el bot ahora.

Además, el encargado necesita una forma rápida de ver **el estado de su sector en
el turno** (no solo las incidencias abiertas que ya da `/abiertas`, sino también
novedades y notas de huésped, en una sola vista).

## Decisiones (del brainstorming)

- **Alcance del piloto**: un solo sector, definido por quién está cargado en
  `employees.json`. Sin código de restricción — el bot ya scoping todo por
  departamento (permisos, `/abiertas`, notificaciones).
- **Corte bot/Sheets**: el informe de turno por el bot llega hasta el **encargado
  de sector**. El aviso al **gerente general** se apaga en el piloto (lo consume
  por Sheets), detrás de un flag reversible.
- **Formato del informe**: se mantiene el **per-persona** actual + se agrega un
  **rollup de sector on-demand** (read-only).
- **Rollup = solo lectura**: NO crea ni cierra un REP, NO linkea ítems, NO cambia
  estados. Evita el conflicto de doble consumo con los informes per-persona.

## Cambios

### 1. Apagar aviso al gerente general — `config/settings.py`, `report_processor.py`

- `config/settings.py`: nuevo flag
  `REPORT_NOTIFY_GERENTE = os.environ.get("REPORT_NOTIFY_GERENTE", "false").lower() == "true"`
  (default `False` en el piloto).
- `report_processor.notify_manager_report`: la rama del `Role.GERENTE_GENERAL`
  solo se ejecuta si `settings.REPORT_NOTIFY_GERENTE` es `True`. El encargado del
  depto del autor sigue recibiendo siempre. Al escalar, se prende el flag por env
  — sin tocar código.

### 2. Rollup de sector on-demand — `handlers/command_handler.py`, `report_processor.py`

Nuevo subcomando **`/reporte sector [ventana]`** (ej. `/reporte sector`,
`/reporte sector 6h`).

- **Parsing** (`handle_reporte`): antes de las ramas `\d+h` y `REP-N`, detectar
  `args[0].lower() == "sector"`; la ventana opcional es `args[1]` (default 24h).
- **Permisos**: encargado (solo sobre su propio depto) y gerente general.
  Empleado → mensaje de rechazo. Reutilizar `permissions.is_manager` /
  `can_query_department`.
- **Datos**: nueva query en `storage` que trae los ítems del **departamento** (no
  del empleado) en la ventana, de los tres tipos (INCIDENCIA/OBSERVACION/
  GUEST_INTEL), **sin filtrar por `report_id`** (incluye ya-consolidados). El
  departamento del ítem se resuelve con `permissions._incident_department`
  (categoría → depto) para incidencias; para OBSERVACION/GUEST_INTEL se usa
  `employee_dept` del que reportó (no tienen categoría de destino).
- **Formato**: función nueva en `report_processor` (ej. `render_sector_rollup`)
  que reutiliza la maquinaria de `render_shift_report` con:
  - Cabecera `📋 ESTADO DEL SECTOR — <depto>` + rango horario + totales (en vez de
    autor).
  - Las mismas secciones (incidencias con estado+emoji, notas de huésped,
    novedades).
  - **Sin** footer de "Cerrado …" (no es un REP). El bloque de incidencias
    abiertas se mantiene como "⏳ Abiertas en el sector".
- **Read-only**: no toca la DB.

### 3. Sheets — sin cambios de código

El informe per-persona ya sincroniza a la hoja "Reportes de turno"
(`sheets_sync.sync_reporte`). La visibilidad del gerente general + dueños es dar
**acceso de lectura a la hoja** (permisos de Google Sheets). No hay trabajo de
código en esta iteración.

### 4. `/help` — documentar el subcomando

Agregar `/reporte sector [ventana]` a la ayuda del encargado.

## Testing

- **notify_manager_report + flag**: con `REPORT_NOTIFY_GERENTE=False` no avisa al
  gerente general pero sí al encargado del depto; con `True` avisa a ambos (como
  hoy, gateado por el modo del gerente).
- **`/reporte sector` permisos**: encargado ve su sector; gerente general ve;
  empleado rechazado; encargado no puede pedir el rollup de otro depto.
- **`/reporte sector` datos/formato**: incluye los tres tipos del sector en la
  ventana (incl. ítems ya consolidados en REPs); cabecera de sector; sin footer de
  cierre; ventana override funciona.
- **Read-only**: ejecutar `/reporte sector` no crea filas en `reports` ni cambia
  `report_id`/`estado` de ninguna clasificación.
- **E2E (`tests/test_hotel_scenarios.py`)**: varios empleados del sector cargan
  incidencia + novedad + nota de huésped → el encargado hace `/reporte sector` y
  ve el rollup combinado; un empleado cierra su `/reporte` per-persona y el gerente
  general **no** lo recibe por el bot (flag off).

## Fuera de alcance (v1)

- Pestaña de rollup por sector en Google Sheets (la visibilidad arriba es por
  permisos de la hoja del per-persona).
- Escalado multi-sector automático / agregación cross-sector.
- Rollup cerrable que consolide los ítems del equipo en un REP (se descartó por el
  conflicto de doble consumo).
