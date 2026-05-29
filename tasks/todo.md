# Estado del proyecto — hotel-bot-mvp

Rama activa: `feat/sprints-b3-b4-b5`

## Sprints completados

| Sprint | Descripción | Commit |
|--------|-------------|--------|
| A.1–A.2 | Cerebro IA (classifier, transcriber, brain) | — |
| A.2.5 | Debug mode | — |
| A.2.6 | Áreas comunes | — |
| A.1.5 | Corrección de reportes | — |
| A.1.5 Dept Bias | Sesgo de departamento | — |
| B.1 | Roles y permisos | — |
| B.2 | Notificaciones | — |
| B.3 | Botones de acción en incidencias | — |
| B.4 | Comandos de consulta (/abiertas, /hab, /buscar) | — |
| B.5 | Reportes de turno retrospectivos (/reporte, /fin) | `038aaa7` |
| B.5.1 | Hardening pre-piloto (4 fixes de seguridad) | `dd14610` |
| B.8 | Sync a Google Sheets (capa de visibilidad) | `27a2749` |

## Refactor integral (post-B.8)

| Fase | Descripción | Commit |
|------|-------------|--------|
| A | Enums (StrEnum × 5), state helpers dedup, init_db once, asyncio.gather paralelo | `910dbc3` |
| B | Capas: `presenters/`, `handlers/_flow`+`_corrections`, `notifier/` (5 módulos) | `d7947e5` |
| C | `storage/` por dominio (10 módulos) + scaffold de migrations versionadas | `93dddcc` |
| Extras | `domain/entities.py` + `notifier/sender.py` (MessageSender port) | `f9ae5e9` |

**Métricas post-refactor:**
- Handlers: 564 → 152 LoC (-73%)
- `storage.py` 733 LoC → paquete con módulos por dominio
- 178 tests verdes en suite normal (incluye 6 escenarios hoteleros E2E fake)
- Cero cambios de comportamiento
- Suite completa con integration: 183 tests totales si se corre `venv/bin/pytest -q -o addopts=''`

## Próximo

Sin sprint planificado. **Fase de testeo con segundo teléfono (Juan, GERENTE_GENERAL).**

## Notas de testing activo

- `employees.json` tiene 9 empleados: 7 ficticios + Jaime (7391337590, ENCARGADO SPA) + Juan (8709342265, GERENTE_GENERAL)
- `NOTIFICATION_REDIRECT_MODE=off` para producción real (sin banner de testing)
- Google Sheets API habilitada en proyecto GCP 726520795387
- 4 hojas en Sheet: Incidencias (UPSERT), Guest Intel, Observaciones, Reportes de turno
- `tests/test_hotel_scenarios.py` automatiza el protocolo manual hotelero: reportar, confirmar, consultar, actuar, cerrar, rechazar permisos, consolidar `/reporte` y auditar `/historial`
- Bug pre-piloto corregido: `/historial` necesitaba importar el módulo `permissions` además de funciones puntuales

## Decisiones explícitas pendientes (postpone hasta tener feedback de campo)

- Reconstrucción full Clean Architecture: descartada. El refactor A/B/C cubre el 80% del valor sin la ceremonia. Solo justifica si se quiere swap de proveedor IA, multi-hotel o equipo de 3+ devs.
- Schema SQLite: no se toca (`report_messages` deprecated quedó, `huesped_afectado` sigue como int). Migrations versionadas listas en `storage/migrations.py` para cuando haga falta.
