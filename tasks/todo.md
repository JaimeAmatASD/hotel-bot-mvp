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

## Próximo

Sin sprint planificado. En fase de testeo con hotel real.

## Notas de testing activo

- `employees.json` tiene 9 empleados: 7 ficticios + Jaime (7391337590) + Juan (8709342265, GERENTE_GENERAL)
- `NOTIFICATION_REDIRECT_MODE=off` para producción real
- Google Sheets API habilitada en proyecto GCP 726520795387
