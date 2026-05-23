from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from handlers import get_employee
from storage import save
import notifier
import permissions
import storage
import report_processor


_EXPECTED_FROM = {
    "tomar":   ["ABIERTA"],
    "proceso": ["ABIERTA", "ASIGNADA"],
    "cerrar":  ["ABIERTA", "ASIGNADA", "EN_PROCESO"],
}

_STATE_MAP = {"tomar": "ASIGNADA", "proceso": "EN_PROCESO", "cerrar": "CERRADA"}


async def _handle_incident_action(query, context) -> None:
    """Handles incident_action:{incident_id}:{sub_action}:{actor_telegram_id} callbacks."""
    parts = query.data.split(":")
    if len(parts) != 4:
        await query.answer("Formato de acción inválido", show_alert=True)
        return

    _, incident_id_str, sub_action, actor_id_str = parts
    try:
        incident_id = int(incident_id_str)
        actor_telegram_id = int(actor_id_str)
    except ValueError:
        await query.answer("Datos de acción inválidos", show_alert=True)
        return

    employees = context.bot_data["employees"]
    actor = employees.get(actor_telegram_id)
    incident = storage.get_incident(incident_id)

    if not actor or not incident:
        await query.answer("Error interno: datos no encontrados", show_alert=True)
        return

    if not permissions.can_act_on_incident(actor, incident):
        storage.save_event(
            incident_id=incident_id,
            actor_telegram_id=actor_telegram_id,
            actor_name=actor.get("nombre"),
            actor_role=actor.get("rol"),
            action="action_rejected_no_permission",
            from_state=incident.get("estado") or "ABIERTA",
            success=False,
            reason=f"rol {actor.get('rol')} no tiene permiso sobre {incident.get('categoria')}",
        )
        await query.answer("No tenés permisos sobre esta incidencia", show_alert=True)
        return

    new_state = _STATE_MAP.get(sub_action)
    if not new_state:
        await query.answer("Acción desconocida", show_alert=True)
        return

    result = storage.update_incident_state_atomic(
        incident_id=incident_id,
        new_state=new_state,
        actor=actor,
        expected_from_states=_EXPECTED_FROM[sub_action],
    )

    if not result["success"]:
        await query.answer(result["reason"], show_alert=True)
        return

    # Reload incident with updated fields
    updated_incident = storage.get_incident(incident_id)

    # Attach assignee name for display
    if updated_incident.get("assigned_to_telegram_id"):
        assignee = employees.get(int(updated_incident["assigned_to_telegram_id"]))
        if assignee:
            updated_incident["_assignee_name"] = assignee.get("nombre", "")

    # Find the original reporter for the notification format
    reporter_name = updated_incident.get("employee_name", "")
    reporter = next(
        (emp for emp in employees.values() if emp.get("nombre") == reporter_name),
        {"nombre": reporter_name, "departamento": updated_incident.get("employee_dept", "")},
    )

    display_id = storage.generate_display_id("INCIDENCIA", incident_id)
    msg, keyboard = notifier.format_notification_message(
        incident=updated_incident,
        reporter=reporter,
        incident_id_display=display_id,
        actual_recipient_telegram_id=actor_telegram_id,
    )

    try:
        if query.message.photo:
            await query.edit_message_caption(caption=msg, reply_markup=keyboard)
        else:
            await query.edit_message_text(text=msg, reply_markup=keyboard)
    except Exception:
        pass  # message unchanged is not a fatal error

    await notifier.notify_employee_state_change(
        bot=context.bot,
        incident=updated_incident,
        new_state=new_state,
        actor_name=actor.get("nombre", ""),
        employees=employees,
    )

    await query.answer()


async def _handle_report_confirm(query, context) -> None:
    pending = context.user_data.get("pending_report_items", {})
    items = pending.get("items", [])
    hours = pending.get("hours", 12)
    employees = context.bot_data["employees"]
    tid = query.from_user.id
    employee = employees.get(tid) or {"nombre": "", "departamento": "", "telegram_id": tid}

    await query.edit_message_reply_markup(reply_markup=None)
    await query.answer()

    report_id = storage.create_report(employee)
    classification_ids = [i["id"] for i in items]
    storage.link_classifications_to_report(classification_ids, report_id)
    context.user_data.pop("pending_report_items", None)

    report = storage.get_report_with_items(report_id)
    display_id = storage.generate_display_id("REPORT", report_id)
    nombre = employee.get("nombre", "").split()[0] or "empleado"

    await report_processor.notify_manager_report(context.bot, report, items, employees)

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"📋 {display_id} creado. Gracias, {nombre}.",
    )


async def _handle_report_correct_start(query, context) -> None:
    pending = context.user_data.get("pending_report_items", {})
    items = pending.get("items", [])
    hours = pending.get("hours", 12)
    n = len(items)

    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)

    context.user_data["awaiting_correction_item"] = {
        "report_items": items,
        "hours": hours,
        "started_at": datetime.now().isoformat(),
    }
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"¿Qué ítem corregís? Mandame el número (1-{n}).",
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action = query.data

    if action.startswith("incident_action:"):
        await _handle_incident_action(query, context)
        return

    if action == "report_confirm_all":
        await _handle_report_confirm(query, context)
        return

    if action == "report_correct":
        await _handle_report_correct_start(query, context)
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
        await query.edit_message_text(f"✅ Guardado. Gracias, {nombre}.")

        if result.get("tipo") == "INCIDENCIA":
            storage.save_event(
                incident_id=incident_id,
                actor_telegram_id=employee.get("telegram_id", 0),
                actor_name=employee.get("nombre"),
                actor_role=employee.get("rol", "EMPLEADO"),
                action="created",
                to_state="ABIERTA",
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

    elif action == "correct":
        context.user_data["awaiting_correction"] = True
        context.user_data["correction_started_at"] = datetime.now().isoformat()
        await query.edit_message_text(
            "✏️ Decime qué corregir o agregar (texto o audio). Recuerdo lo que reportaste antes y lo reproceso con tu corrección."
        )
