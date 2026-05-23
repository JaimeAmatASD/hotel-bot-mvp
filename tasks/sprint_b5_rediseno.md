# Sprint B.5 Rediseño — Reportes de turno retrospectivos

## Problema

El B.5 original implementaba un modo acumulativo: el empleado abría un "reporte",
acumulaba mensajes crudos, y los clasificaba al final del turno. Esto retrasaba las
notificaciones de incidencias hasta el cierre, rompiendo el principio BASE PRIMERO.

## Nuevo diseño

El reporte es un resumen retrospectivo. Los empleados reportan normalmente durante
el turno (flujo individual sin cambios). Al final, /reporte consolida los ítems
ya clasificados del empleado en una ventana de tiempo.

## Checklist

### config/settings.py
- [x] Eliminar REPORT_OPEN_KEYWORDS, REPORT_CLOSE_KEYWORDS, REPORT_TIMEOUT_HOURS

### storage.py — eliminar obsoleto
- [x] Eliminar get_expired_open_reports
- [x] Eliminar add_message_to_report, get_report_messages
- [x] Eliminar open_report, get_open_report_for_employee
- [x] Ajustar get_report_with_items (messages: [] sin borrar tabla)

### storage.py — agregar nuevo
- [x] get_classifications_for_employee_recent(employee_name, hours, exclude_in_report)
- [x] update_classification(classification_id, result)
- [x] link_classifications_to_report(classification_ids, report_id)  [batch]
- [x] create_report(employee) → int  [status=CLOSED de entrada]

### report_processor.py — reescribir
- [x] Eliminar: _normalize, is_open_keyword, is_close_keyword
- [x] Eliminar: process_report_at_closure, save_confirmed_report_items, _regroup_items, close_report_with_timeout
- [x] Reescribir format_report_summary(items, employee, hours)
- [x] Reescribir format_report_for_manager(report, items, display_id)
- [x] Crear consolidate_recent_classifications(employee_name, hours)

### bot.py
- [x] Eliminar check_expired_reports y job_queue.run_repeating

### handlers/text_handler.py
- [x] Eliminar _do_report_open, _do_report_close
- [x] Eliminar branching acumulativo (awaiting_report_correction, open_report, is_open_keyword)
- [x] Agregar detección awaiting_correction_item (esperando número)
- [x] Agregar detección awaiting_item_correction (esperando texto de corrección)

### handlers/audio_handler.py
- [x] Eliminar bloque open_report mode
- [x] Agregar awaiting_correction_item y awaiting_item_correction

### handlers/photo_handler.py
- [x] Eliminar bloque open_report mode

### handlers/command_handler.py
- [x] Reescribir handle_reporte (nuevo flujo: sin args=12h, 6h, 24h, REP-N=vista)
- [x] Reescribir handle_fin (alias puro de handle_reporte sin args)

### handlers/callback_handler.py
- [x] Reescribir _handle_report_confirm (create_report + link batch + notif gerente)
- [x] Reescribir _handle_report_correct_start (pedir número de ítem)
- [x] Agregar _handle_report_item_blocked (bloqueo para INCIDENCIAs)

### tests/test_reports.py — reescribir (9 tests)
- [x] T1: /reporte sin ítems → "no reportaste nada"
- [x] T2: /reporte 6h con ítems → resumen agrupado correcto
- [x] T3: ítems en REP existente → excluidos
- [x] T4: "Todo bien" → crea REP-N, link batch, notifica gerente si mode=todo
- [x] T5: "Corregir" + INC → mensaje de bloqueo
- [x] T6: "Corregir" + OBS → reprocesa + UPDATE + re-muestra resumen
- [x] T7: NOTIFICATION_REDIRECT_MODE respetado
- [x] T8: permisos /reporte REP-N (EMPLEADO/ENCARGADO/GERENTE)
- [x] T9: /fin → equivalente a /reporte sin args

### Verificación
- [x] pytest tests/ verde sin regresiones
- [x] pytest tests/test_reports.py verde
- [x] bot.py arranca sin error de job_queue

## Decisiones clave

- create_report inserta con status='CLOSED' — no hay reportes abiertos en DB
- Items viven en user_data, no en callback_data (límite 64 bytes en Telegram)
- get_classifications_for_employee_recent usa employee_name, no telegram_id
- Corrección de ítem reutiliza mecanismo A.1 (process_message con previous_context)
- /fin llama handle_reporte con context.args = [] — sin duplicar lógica
