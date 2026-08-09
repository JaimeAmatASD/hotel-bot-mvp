import asyncio
import logging
from datetime import date, datetime
from telegram import Update
from telegram.ext import ContextTypes
from handlers import get_employee
from storage import save
from config.enums import IncidentState, ReportType
from config.transitions import ACTION_TO_STATE, EXPECTED_FROM
import notifier
import permissions
import storage
import report_processor
import sheets_sync
from permissions import _incident_department

logger = logging.getLogger(__name__)


def _attach_assignee_name(incident: dict, employees: dict) -> dict:
    if incident.get("assigned_to_telegram_id"):
        a = employees.get(int(incident["assigned_to_telegram_id"]))
        if a:
            incident["_assignee_name"] = a.get("nombre", "")
    return incident


def _find_reporter(incident: dict, employees: dict) -> dict:
    reporter_tid = incident.get("employee_telegram_id")
    if reporter_tid is not None:
        try:
            emp = employees.get(int(reporter_tid))
            if emp:
                return emp
        except (TypeError, ValueError):
            pass
    reporter_name = incident.get("employee_name", "")
    return next(
        (emp for emp in employees.values() if emp.get("nombre") == reporter_name),
        {"nombre": reporter_name, "departamento": incident.get("employee_dept", "")},
    )


async def _refresh_message(query, incident, employees, actor_tid):
    display_id = storage.generate_display_id(ReportType.INCIDENCIA, incident["id"])
    reporter = _find_reporter(incident, employees)
    msg, keyboard = notifier.format_notification_message(
        incident=incident, reporter=reporter, incident_id_display=display_id,
        actual_recipient_telegram_id=actor_tid,
    )
    try:
        if query.message.photo:
            await query.edit_message_caption(caption=msg, reply_markup=keyboard)
        else:
            await query.edit_message_text(text=msg, reply_markup=keyboard)
    except Exception as e:
        logger.warning("No se pudo refrescar el mensaje de %s: %s", display_id, e)
    return display_id


async def _handle_incident_action(query, context) -> None:
    """incident_action:{incident_id}:{action}. Action ∈ verbos de transición o asignar/reasignar."""
    parts = query.data.split(":")
    if len(parts) != 3:
        await query.answer("Formato de acción inválido", show_alert=True)
        return
    _, incident_id_str, action = parts
    try:
        incident_id = int(incident_id_str)
    except ValueError:
        await query.answer("Datos de acción inválidos", show_alert=True)
        return

    actor_telegram_id = query.from_user.id
    employees = context.bot_data["employees"]
    actor = employees.get(actor_telegram_id)
    incident = storage.get_incident(incident_id)
    if not actor or not incident:
        await query.answer("Error interno: datos no encontrados", show_alert=True)
        return

    if not permissions.can_do_action(actor, incident, action):
        storage.save_event(
            incident_id=incident_id, actor_telegram_id=actor_telegram_id,
            actor_name=actor.get("nombre"), actor_role=actor.get("rol"),
            action="action_rejected_no_permission",
            from_state=incident.get("estado") or "NUEVA", success=False,
            reason=f"rol {actor.get('rol')} sin permiso para {action}",
        )
        await query.answer("No tenés permisos sobre esta incidencia", show_alert=True)
        return

    # asignar/reasignar abren el picker, no transicionan
    if action in ("asignar", "reasignar"):
        await _show_assign_picker(query, context, incident_id, incident, actor)
        return

    new_state = ACTION_TO_STATE.get(action)
    if not new_state:
        await query.answer("Acción desconocida", show_alert=True)
        return

    result = storage.update_incident_state_atomic(
        incident_id=incident_id, new_state=new_state, actor=actor,
        expected_from_states=EXPECTED_FROM[action], action=action,
    )
    if not result["success"]:
        await query.answer(result["reason"], show_alert=True)
        return

    updated = _attach_assignee_name(storage.get_incident(incident_id), employees)
    display_id = await _refresh_message(query, updated, employees, actor_telegram_id)

    await notifier.notify_employee_state_change(
        bot=context.bot, incident=updated, new_state=new_state,
        actor_name=actor.get("nombre", ""), employees=employees,
    )
    if new_state == IncidentState.RESUELTA:
        await notifier.notify_managers_resolved(
            bot=context.bot, incident=updated, actor_name=actor.get("nombre", ""), employees=employees)

    await query.answer()
    asyncio.create_task(sheets_sync.sync_incidencia(updated, display_id, employees))


async def _show_assign_picker(query, context, incident_id, incident, actor):
    employees = context.bot_data["employees"]
    if actor.get("rol") == "GERENTE_GENERAL":
        depts = permissions.assignable_departments(actor, employees)
        kb = notifier.build_dept_menu_keyboard(incident_id, depts)
    else:
        dept = _incident_department(incident)
        targets = [(tid, e.get("nombre", "")) for tid, e in
                   permissions.assignable_targets(actor, employees, dept)]
        kb = notifier.build_assign_keyboard(incident_id, targets)
    try:
        await query.edit_message_reply_markup(reply_markup=kb)
    except Exception as e:
        logger.warning("No se pudo mostrar el picker de asignación de INC-%s: %s", incident_id, e)
    await query.answer("Elegí a quién asignar")


async def _handle_assign_dept(query, context) -> None:
    """assign_dept:{incident_id}:{DEPTO} — gerente eligió depto, mostrar personas."""
    parts = query.data.split(":")
    if len(parts) != 3:
        await query.answer("Datos de asignación inválidos", show_alert=True)
        return
    _, incident_id_str, dept = parts
    try:
        incident_id = int(incident_id_str)
    except ValueError:
        await query.answer("Datos de asignación inválidos", show_alert=True)
        return
    employees = context.bot_data["employees"]
    actor = employees.get(query.from_user.id)
    incident = storage.get_incident(incident_id)
    if not actor or not incident or not permissions.can_do_action(actor, incident, "asignar"):
        await query.answer("No tenés permisos", show_alert=True)
        return
    # Solo el gerente elige depto libremente; el encargado queda dentro del depto de la incidencia.
    if actor.get("rol") != "GERENTE_GENERAL" and dept != _incident_department(incident):
        await query.answer("No tenés permisos sobre ese departamento", show_alert=True)
        return
    targets = [(tid, e.get("nombre", "")) for tid, e in
               permissions.assignable_targets(actor, employees, dept)]
    kb = notifier.build_assign_keyboard(incident_id, targets)
    try:
        await query.edit_message_reply_markup(reply_markup=kb)
    except Exception as e:
        logger.warning("No se pudo mostrar el picker de depto de INC-%s: %s", incident_id, e)
    await query.answer()


async def _handle_assign_to(query, context) -> None:
    """assign_to:{incident_id}:{telegram_id} — asignación efectiva."""
    parts = query.data.split(":")
    if len(parts) != 3:
        await query.answer("Datos de asignación inválidos", show_alert=True)
        return
    try:
        incident_id = int(parts[1])
        target_tid = int(parts[2])
    except ValueError:
        await query.answer("Datos de asignación inválidos", show_alert=True)
        return
    employees = context.bot_data["employees"]
    actor = employees.get(query.from_user.id)
    incident = storage.get_incident(incident_id)
    if not actor or not incident or not permissions.can_do_action(actor, incident, "asignar"):
        await query.answer("No tenés permisos", show_alert=True)
        return

    target = employees.get(target_tid)
    if not target:
        await query.answer("Destinatario inválido", show_alert=True)
        return
    # El encargado solo asigna dentro del depto de la incidencia; el gerente, a cualquiera.
    if actor.get("rol") != "GERENTE_GENERAL" and target.get("departamento") != _incident_department(incident):
        await query.answer("No podés asignar fuera de tu departamento", show_alert=True)
        return

    result = storage.update_incident_state_atomic(
        incident_id=incident_id, new_state=IncidentState.ASIGNADA, actor=actor,
        expected_from_states=EXPECTED_FROM["asignar"], action="asignar",
        assignee_telegram_id=target_tid,
    )
    if not result["success"]:
        await query.answer(result["reason"], show_alert=True)
        return

    updated = _attach_assignee_name(storage.get_incident(incident_id), employees)
    display_id = await _refresh_message(query, updated, employees, query.from_user.id)
    await notifier.notify_assignee(bot=context.bot, incident=updated, employees=employees)
    await query.answer("Asignada")
    asyncio.create_task(sheets_sync.sync_incidencia(updated, display_id, employees))


async def _handle_report_confirm(query, context) -> None:
    pending = context.user_data.get("pending_report_items", {})
    items = pending.get("items", [])
    employees = context.bot_data["employees"]
    tid = query.from_user.id
    employee = employees.get(tid) or {"nombre": "", "departamento": "", "telegram_id": tid}

    await query.edit_message_reply_markup(reply_markup=None)
    await query.answer()

    # Upsert: volver a cerrar el informe de hoy actualiza el mismo REP, no crea otro.
    # El arrastre no va en `items`, así que no se re-linkea: cada ítem pertenece al
    # informe del día en que se cargó.
    day = pending.get("day") or date.today().isoformat()
    report_id = storage.upsert_report_for_day(employee, day)
    classification_ids = [i["id"] for i in items]
    storage.link_classifications_to_report(classification_ids, report_id)
    context.user_data.pop("pending_report_items", None)
    context.user_data.pop("report_draft_open", None)

    report = storage.get_report_with_items(report_id)
    display_id = storage.generate_display_id(ReportType.REPORT, report_id)
    nombre = employee.get("nombre", "").split()[0] or "empleado"

    await report_processor.notify_manager_report(context.bot, report, items, employees)

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"📋 {display_id} creado. Gracias, {nombre}.",
    )
    asyncio.create_task(sheets_sync.sync_reporte(report, items, display_id))


async def _handle_report_add_item(query, context) -> None:
    """No abre ninguna máquina de estados: el ítem entra por el flujo normal y, como la
    ventana del informe es el día entero, aparece solo. La bandera es solo para volver
    a mostrar el borrador sin tipear /reporte otra vez."""
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    context.user_data["report_draft_open"] = True
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Dale, mandame qué querés sumar (texto, audio o foto).",
    )


async def _resend_report_draft(query, context, employee) -> None:
    """Vuelve a mostrar el borrador del día tras sumar un ítem."""
    hoy = date.today().isoformat()
    tid = query.from_user.id
    items = storage.get_classifications_for_employee_day(tid, hoy)
    carryover = storage.get_open_incidents_before_day(tid, hoy)
    context.user_data["pending_report_items"] = {
        "items": items, "carryover": carryover, "day": hoy,
    }
    texto, teclado = report_processor.format_report_summary(items, employee, carryover)
    await context.bot.send_message(
        chat_id=query.message.chat_id, text=texto, reply_markup=teclado)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action = query.data

    if action.startswith("incident_action:"):
        await _handle_incident_action(query, context)
        return

    if action.startswith("assign_to:"):
        await _handle_assign_to(query, context)
        return

    if action.startswith("assign_dept:"):
        await _handle_assign_dept(query, context)
        return

    if action == "report_confirm_all":
        await _handle_report_confirm(query, context)
        return

    if action == "report_add_item":
        await _handle_report_add_item(query, context)
        return

    await query.answer()

    pending = context.user_data.get("pending")

    if action == "confirm":
        if not pending:
            await query.edit_message_text("❌ No hay reporte pendiente.")
            return

        employee = get_employee(update, context)
        result = pending["result"]
        incident_id = save(employee, pending["original_text"], result)
        context.user_data.pop("pending", None)

        nombre = employee["nombre"].split()[0] if employee else "empleado"

        # Para INCIDENCIA y OBSERVACION, enviar respuesta separada (mantiene el resumen visible)
        if result.get("tipo") in (ReportType.INCIDENCIA, ReportType.OBSERVACION):
            await query.answer()
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"✅ Guardado. Gracias, {nombre}."
            )
        else:
            # Para GUEST_INTEL, editar el mensaje original (se borra)
            await query.edit_message_text(f"✅ Guardado. Gracias, {nombre}.")

        if result.get("tipo") == ReportType.INCIDENCIA:
            storage.save_event(
                incident_id=incident_id,
                actor_telegram_id=employee.get("telegram_id", 0),
                actor_name=employee.get("nombre"),
                actor_role=employee.get("rol", "EMPLEADO"),
                action="created",
                to_state=IncidentState.NUEVA,
                success=True,
            )
            incident = {
                **result,
                "id": incident_id,
                "employee_name": employee["nombre"],
                "employee_dept": employee.get("departamento"),
                "photo_path": result.get("_meta", {}).get("photo_path"),
            }
            await notifier.notify_incident(
                bot=context.bot,
                incident=incident,
                employees=context.bot_data["employees"],
                reporter_employee=employee,
            )

        tipo = result.get("tipo")
        if tipo == ReportType.INCIDENCIA:
            fresh_inc = storage.get_incident(incident_id)
            inc_display = storage.generate_display_id(ReportType.INCIDENCIA, incident_id)
            asyncio.create_task(
                sheets_sync.sync_incidencia(fresh_inc, inc_display, context.bot_data.get("employees"))
            )
        elif tipo == ReportType.GUEST_INTEL:
            gi_display = storage.generate_display_id(ReportType.GUEST_INTEL, incident_id)
            asyncio.create_task(sheets_sync.sync_guest_intel(result, employee, gi_display))
        elif tipo == ReportType.OBSERVACION:
            obs_display = storage.generate_display_id(ReportType.OBSERVACION, incident_id)
            asyncio.create_task(sheets_sync.sync_observacion(result, employee, obs_display))

        if context.user_data.get("report_draft_open"):
            await _resend_report_draft(query, context, employee)

    elif action == "correct":
        context.user_data["awaiting_correction"] = True
        context.user_data["correction_started_at"] = datetime.now().isoformat()
        await query.edit_message_text(
            "✏️ Decime qué corregir o agregar (texto o audio). Recuerdo lo que reportaste antes y lo reproceso con tu corrección."
        )
