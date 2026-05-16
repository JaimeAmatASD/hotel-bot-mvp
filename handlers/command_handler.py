from telegram import Update
from telegram.ext import ContextTypes
from storage import (
    get_debug_mode, set_debug_mode,
    get_notification_preferences, set_notification_mode, toggle_excluded_department,
    get_open_incidents, get_incidents_for_room, get_guest_intel_for_room,
    get_observations_for_room, search_classifications,
)
from permissions import get_role, filter_visible_incidents, can_query_department, _incident_department
from handlers import (
    format_incident_list, format_room_view, get_help_text, format_incident_history,
)


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

    if role != "GERENTE_GENERAL":
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
    valid_modes = {"todo", "criticas", "solo_criticas", "nada"}

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

    open_states = {"ABIERTA", "ASIGNADA", "EN_PROCESO"}
    incidents_open = [i for i in visible if (i.get("estado") or "ABIERTA") in open_states]
    incidents_closed = [i for i in visible if (i.get("estado") or "ABIERTA") == "CERRADA"]

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
