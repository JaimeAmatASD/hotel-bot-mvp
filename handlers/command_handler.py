from telegram import Update
from telegram.ext import ContextTypes
from storage import (
    get_debug_mode, set_debug_mode,
    get_notification_preferences, set_notification_mode, toggle_excluded_department,
    get_open_incidents, get_incidents_for_room, get_guest_intel_for_room,
    get_observations_for_room, search_classifications,
)
from permissions import get_role, filter_visible_incidents, can_query_department, _incident_department
from config.enums import IncidentState, Role, NotificationMode, ReportType
from handlers import (
    format_incident_line, format_incident_list, format_room_view, get_help_text,
    format_incident_history,
)
from notifier import build_keyboard_for_state
import re
import storage
import permissions
import report_processor


async def handle_debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    args = context.args  # list of words after /debug

    if args and args[0].lower() == "on":
        set_debug_mode(tid, True)
        await update.message.reply_text(
            "🔍 Modo debug activado. Verás detalles técnicos en cada reporte."
        )
    elif args and args[0].lower() == "off":
        set_debug_mode(tid, False)
        await update.message.reply_text(
            "✅ Modo debug desactivado. Volvés a la vista normal."
        )
    else:
        current = get_debug_mode(tid)
        estado = "activado 🔍" if current else "desactivado ✅"
        await update.message.reply_text(
            f"Modo debug: <b>{estado}</b>\n\n"
            "Comandos:\n"
            "• /debug on — activar\n"
            "• /debug off — desactivar",
            parse_mode="HTML",
        )


async def handle_notificaciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    employees = context.bot_data.get("employees", {})
    role = get_role(tid, employees)

    if role != Role.GERENTE_GENERAL:
        await update.message.reply_text("Este comando es solo para el gerente general.")
        return

    args = context.args or []

    if not args:
        prefs = get_notification_preferences(tid)
        mode = prefs["mode"]
        excluded = prefs["excluded_departments"]
        excluded_str = ", ".join(excluded) if excluded else "ninguno"
        await update.message.reply_text(
            f"🔔 <b>Configuración de notificaciones</b>\n\n"
            f"Modo actual: <b>{mode}</b>\n"
            f"Departamentos excluidos: {excluded_str}\n\n"
            f"Opciones:\n"
            f"• /notificaciones todo — todas las incidencias\n"
            f"• /notificaciones criticas — solo CRITICA y ALTA (default)\n"
            f"• /notificaciones solo_criticas — solo CRITICA\n"
            f"• /notificaciones nada — sin notificaciones en tiempo real\n"
            f"• /notificaciones depto NOMBRE — excluir/incluir un departamento",
            parse_mode="HTML",
        )
        return

    cmd = args[0].lower()
    valid_modes = {m.value for m in NotificationMode}

    if cmd in valid_modes:
        set_notification_mode(tid, cmd)
        await update.message.reply_text(f"✅ Modo de notificaciones: <b>{cmd}</b>", parse_mode="HTML")
        return

    if cmd == "depto" and len(args) >= 2:
        dept = args[1].upper()
        is_excluded = toggle_excluded_department(tid, dept)
        estado = "excluido ❌" if is_excluded else "incluido ✅"
        await update.message.reply_text(f"Departamento <b>{dept}</b>: {estado}", parse_mode="HTML")
        return

    await update.message.reply_text(
        "Opción no reconocida. Usá /notificaciones para ver las opciones."
    )


_KNOWN_PRIORITIES = {"CRITICA", "ALTA", "MEDIA", "BAJA"}


async def handle_abiertas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    employees = context.bot_data.get("employees", {})
    user = employees.get(tid)
    if not user:
        await update.message.reply_text("No estás registrado en el sistema.")
        return

    args = [a.upper() for a in (context.args or [])]
    prioridad = next((a for a in args if a in _KNOWN_PRIORITIES), None)
    departamento = next((a for a in args if a not in _KNOWN_PRIORITIES), None)

    if departamento and not can_query_department(user, departamento):
        await update.message.reply_text("No tenés acceso a ese departamento.")
        return

    incidents = get_open_incidents(prioridad=prioridad)
    visible = filter_visible_incidents(user, incidents)

    if departamento:
        visible = [i for i in visible if _incident_department(i).upper() == departamento]

    await update.message.reply_text(format_incident_list(visible, employees))


async def handle_hab(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    employees = context.bot_data.get("employees", {})
    user = employees.get(tid)

    args = context.args or []
    if not args:
        await update.message.reply_text("Usá /hab 305 o /hab lobby.")
        return

    room = " ".join(args)
    all_incidents = get_incidents_for_room(room)
    visible = filter_visible_incidents(user, all_incidents) if user else all_incidents

    open_states = {IncidentState.NUEVA, IncidentState.ASIGNADA, IncidentState.EN_PROCESO, IncidentState.RESUELTA}
    incidents_open = [i for i in visible if (i.get("estado") or IncidentState.NUEVA) in open_states]
    incidents_closed = [i for i in visible if (i.get("estado") or IncidentState.NUEVA) == IncidentState.CERRADA]

    guest_intel = get_guest_intel_for_room(room)
    observations = get_observations_for_room(room)

    if not any([visible, guest_intel, observations]):
        await update.message.reply_text(f"🛏️ {room} — sin actividad registrada.")
        return

    text = format_room_view(
        room=room,
        incidents_open=incidents_open,
        incidents_closed=incidents_closed,
        guest_intel=guest_intel,
        observations=observations,
        employees=employees,
    )
    await update.message.reply_text(text)


async def handle_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    employees = context.bot_data.get("employees", {})
    user = employees.get(tid)

    args = context.args or []
    query = " ".join(args).strip()

    if len(query) < 3:
        await update.message.reply_text("🔍 Necesito al menos 3 letras para buscar.")
        return

    results = search_classifications(query)
    visible = filter_visible_incidents(user, results) if user else results

    if not visible:
        await update.message.reply_text(f"🔍 No encontré nada con '{query}'.")
        return

    await update.message.reply_text(format_incident_list(visible, employees))


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    employees = context.bot_data.get("employees", {})
    user = employees.get(tid)
    role = user.get("rol", "EMPLEADO") if user else "EMPLEADO"
    department = user.get("departamento") if user else None
    await update.message.reply_text(get_help_text(role, department))


async def handle_mistareas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista las incidencias asignadas al usuario, cada una con sus botones."""
    tid = update.effective_user.id
    employees = context.bot_data.get("employees", {})
    user = employees.get(tid)
    if not user:
        await update.message.reply_text("No estás registrado en el sistema.")
        return

    tareas = storage.get_incidents_assigned_to(tid)
    if not tareas:
        await update.message.reply_text("✅ No tenés tareas asignadas pendientes.")
        return

    await update.message.reply_text(f"🧰 Tenés {len(tareas)} tarea(s) asignada(s):")
    for inc in tareas:
        keyboard = build_keyboard_for_state(inc["id"], inc.get("estado") or IncidentState.ASIGNADA)
        await update.message.reply_text(
            format_incident_line(inc, employees), reply_markup=keyboard
        )


async def handle_porvalidar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cola de validación del gerente/encargado: incidencias RESUELTA de su alcance."""
    tid = update.effective_user.id
    employees = context.bot_data.get("employees", {})
    user = employees.get(tid)
    if not user:
        await update.message.reply_text("No estás registrado en el sistema.")
        return
    if not permissions.is_manager(tid, employees):
        await update.message.reply_text(
            "Solo encargados y gerentes validan incidencias."
        )
        return

    pendientes = filter_visible_incidents(user, storage.get_resolved_incidents())
    if not pendientes:
        await update.message.reply_text("✅ No hay incidencias esperando validación.")
        return

    await update.message.reply_text(
        f"📋 {len(pendientes)} incidencia(s) esperando tu validación:"
    )
    for inc in pendientes:
        keyboard = build_keyboard_for_state(inc["id"], IncidentState.RESUELTA)
        await update.message.reply_text(
            format_incident_line(inc, employees), reply_markup=keyboard
        )


_DEFAULT_HOURS = 12


async def handle_reporte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    employees = context.bot_data.get("employees", {})
    user = employees.get(tid)
    args = context.args or []

    if args:
        arg = args[0]

        # /reporte 6h / 24h → consolidation with custom window
        if re.fullmatch(r"\d+h", arg, re.IGNORECASE):
            hours = int(arg[:-1])
            if not user:
                await update.message.reply_text("❌ No estás registrado.")
                return
            items = report_processor.consolidate_recent_classifications(user["nombre"], hours)
            if not items:
                await update.message.reply_text(
                    f"No reportaste nada en las últimas {hours}h. ¿Querés ampliar? `/reporte {hours * 2}h`",
                    parse_mode="Markdown",
                )
                return
            context.user_data["pending_report_items"] = {"items": items, "hours": hours}
            text, keyboard = report_processor.format_report_summary(items, user, hours)
            await update.message.reply_text(text, reply_markup=keyboard)
            return

        # /reporte REP-N → view existing report
        raw = arg.upper().removeprefix("REP-")
        try:
            report_id = int(raw)
        except ValueError:
            await update.message.reply_text("Usá /reporte, /reporte 6h, o /reporte REP-N.")
            return

        report = storage.get_report_with_items(report_id)
        if not report:
            await update.message.reply_text(f"No encontré REP-{report_id}.")
            return

        if user:
            role = user.get("rol", Role.EMPLEADO)
            if role == Role.EMPLEADO and report.get("employee_telegram_id") != tid:
                await update.message.reply_text("No tenés permiso para ver ese reporte.")
                return
            if role == Role.ENCARGADO:
                report_dept = report.get("employee_department")
                if report_dept and report_dept != user.get("departamento"):
                    await update.message.reply_text("No tenés permiso para ver ese reporte.")
                    return

        display_id = storage.generate_display_id(ReportType.REPORT, report_id)
        text = report_processor.render_shift_report(
            report.get("items", []), display_id=display_id,
            employee_name=report.get("employee_name", ""),
            department=report.get("employee_department"),
            closed_at=report.get("closed_at"),
        )
        await update.message.reply_text(text)
        return

    # /reporte sin args → consolidate last DEFAULT_HOURS
    if not user:
        await update.message.reply_text("❌ No estás registrado.")
        return

    hours = _DEFAULT_HOURS
    items = report_processor.consolidate_recent_classifications(user["nombre"], hours)
    if not items:
        await update.message.reply_text(
            f"No reportaste nada en las últimas {hours}h. ¿Querés ampliar? `/reporte 24h`",
            parse_mode="Markdown",
        )
        return

    context.user_data["pending_report_items"] = {"items": items, "hours": hours}
    text, keyboard = report_processor.format_report_summary(items, user, hours)
    await update.message.reply_text(text, reply_markup=keyboard)


async def handle_fin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.args = []
    await handle_reporte(update, context)


async def handle_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    employees = context.bot_data.get("employees", {})
    user = employees.get(tid)

    args = context.args or []
    if not args:
        await update.message.reply_text("Usá: /historial INC-N o /historial 142")
        return

    raw = args[0].upper().removeprefix("INC-")
    try:
        incident_id = int(raw)
    except ValueError:
        await update.message.reply_text("ID inválido. Usá formato INC-N o un número.")
        return

    incident = storage.get_incident(incident_id)
    if not incident:
        await update.message.reply_text(f"No encontré INC-{incident_id}.")
        return

    if user and not permissions.can_see_incident(user, incident):
        await update.message.reply_text("No tenés permiso para ver esa incidencia.")
        return

    events = storage.get_events_for_incident(incident_id)
    text = format_incident_history(incident, events)
    await update.message.reply_text(text)
