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
| Work-order lifecycle | 6 estados (NUEVA→ASIGNADA→EN_PROCESO→RESUELTA→CERRADA + CANCELADA), delegación con picker, trazabilidad (assigned_by/resolved_by/...), validar/reabrir | `89f71bc`…`4581bb7` |
| Flujo empleado | EN_PROCESO opcional + `/mistareas` + `/porvalidar` (cola del gerente) | `a096b29`…`38f01c0` |
| Informe de turno | `/reporte` acumulativo con plantilla única + aviso al gerente gateado por `REPORT_NOTIFY_GERENTE` | `0fbeb3e`…`e436a3b` |
| Reporte sector | `/reporte sector` — rollup read-only del sector (encargado/gerente) | `331b0ab`…`9567d78` |

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
- Cero cambios de comportamiento

**Métricas actuales (2026-07-02):**
- 232 tests verdes en suite normal (`venv/bin/pytest -q`), 5 integration deselected
- Suite completa con integration Gemini/Groq: `venv/bin/pytest -q -o addopts=''`
- E2E hoteleros en `tests/test_hotel_scenarios.py`: ciclo work-order completo, delegación, reabrir, permisos, reportes

## Próximo

Sin sprint planificado. **Piloto intra-sector: testeo real con Jaime y Juan (ambos MANTENIMIENTO).** `REPORT_NOTIFY_GERENTE=false` hasta validar el flujo con el encargado.

### Pendientes operativos (post-revisión de seguridad 2026-07-03)

- [ ] Backup diario de `data/hotel_bot.db` (cron con `sqlite3 .backup`)
- [ ] systemd unit para el bot (arranque automático + restart on crash); hoy corre en foreground en terminal
- [ ] Vaciar `bot.log` viejo (`> bot.log`) — contiene el token en las líneas httpx previas al fix `95576e1`; rotar token en BotFather si el log se compartió
- [ ] Al deployar en otra máquina: copiar `config/employees.local.json` (IDs reales, gitignoreado)
- [ ] Roadmap: /start con onboarding, recordatorios de CRITICA sin asignar, migrar consolidación de reportes a telegram_id

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
