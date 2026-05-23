from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import storage
import permissions
from config import settings
from handlers import PRIORIDAD_EMOJI, TIPO_EMOJI


def _time_ago(dt_str: str) -> str:
    try:
        dt = datetime.fromisoformat(dt_str)
        minutes = int((datetime.now() - dt).total_seconds() / 60)
        if minutes < 1:
            return "ahora mismo"
        return f"{minutes} min"
    except Exception:
        return "?"


def build_keyboard_for_state(
    incident_id: int,
    estado: str,
) -> InlineKeyboardMarkup | None:
    cb = lambda action: f"incident_action:{incident_id}:{action}"
    buttons_by_state = {
        "ABIERTA":    [("🙋 Tomar", cb("tomar")), ("⏳ En proceso", cb("proceso")), ("✅ Cerrar", cb("cerrar"))],
        "ASIGNADA":   [("⏳ En proceso", cb("proceso")), ("✅ Cerrar", cb("cerrar"))],
        "EN_PROCESO": [("✅ Cerrar", cb("cerrar"))],
        "CERRADA":    [],
    }
    buttons = buttons_by_state.get(estado, [])
    if not buttons:
        return None
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=data) for label, data in buttons]])


def format_notification_message(
    incident: dict,
    reporter: dict,
    incident_id_display: str,
    is_redirect: bool = False,
    actual_recipient_name: str | None = None,
    actual_recipient_telegram_id: int | None = None,
) -> tuple[str, InlineKeyboardMarkup | None]:
    estado = incident.get("estado", "ABIERTA")
    prioridad = incident.get("prioridad", "")
    categoria = incident.get("categoria", "")
    subcategoria = incident.get("subcategoria")
    ubicacion = incident.get("ubicacion", "")
    descripcion = incident.get("descripcion", "")
    reporter_name = reporter.get("nombre", "")
    reporter_dept = reporter.get("departamento", "")

    cat_str = f"{categoria} › {subcategoria}" if subcategoria else categoria
    prioridad_emoji = PRIORIDAD_EMOJI.get(prioridad, "")
    tipo_emoji = TIPO_EMOJI.get("INCIDENCIA", "🔧")

    # Header varies by state
    if estado == "ABIERTA":
        header = f"🔔 Nueva incidencia — {incident_id_display}"
    elif estado == "ASIGNADA":
        assignee_name = incident.get("_assignee_name", f"ID {incident.get('assigned_to_telegram_id', '?')}")
        header = f"🔔 {incident_id_display} — ASIGNADA a {assignee_name}"
    elif estado == "EN_PROCESO":
        header = f"🔔 {incident_id_display} — EN PROCESO"
    elif estado == "CERRADA":
        header = f"🔔 {incident_id_display} — ✅ CERRADA"
    else:
        header = f"🔔 {incident_id_display}"

    lines = [
        header,
        f"{tipo_emoji} {cat_str} — {prioridad_emoji} {prioridad}",
        f"📍 {ubicacion}",
        f"📝 {descripcion}",
        "",
        f"Reportado por: {reporter_name} ({reporter_dept})",
    ]

    if estado == "ABIERTA":
        created_at = incident.get("timestamp")
        if created_at:
            lines.append(f"Hace: {_time_ago(created_at)}")
    elif estado in ("ASIGNADA", "EN_PROCESO"):
        created_at = incident.get("timestamp")
        if created_at:
            lines.append(f"Hace: {_time_ago(created_at)}")
        assigned_at = incident.get("assigned_at")
        if assigned_at:
            lines.append(f"Asignado: hace {_time_ago(assigned_at)}")
    elif estado == "CERRADA":
        assignee_name = incident.get("_assignee_name", "")
        if assignee_name:
            lines.append(f"Resuelta por: {assignee_name}")
        res_min = incident.get("resolution_time_minutes")
        if res_min is not None:
            lines.append(f"Tiempo de resolución: {res_min} min")

    body = "\n".join(lines)

    if is_redirect and actual_recipient_name:
        prefix = f"🧪 [Modo testing — destinatario real: {actual_recipient_name}]\n\n"
        body = prefix + body

    incident_id = incident.get("id")
    keyboard = None
    if incident_id and actual_recipient_telegram_id:
        keyboard = build_keyboard_for_state(incident_id, estado)

    return body, keyboard


def _should_notify_gerente(incident: dict, prefs: dict) -> bool:
    """Aplica filtros del gerente. CRITICA siempre pasa."""
    prioridad = incident.get("prioridad", "")
    mode = prefs.get("mode", "criticas")

    if prioridad == "CRITICA":
        return True
    if mode == "nada":
        return False
    if mode == "solo_criticas":
        return False
    if mode == "criticas":
        return prioridad == "ALTA"
    if mode == "todo":
        excluded = prefs.get("excluded_departments", [])
        return incident.get("categoria") not in excluded
    return True


async def send_notification_with_logging(
    bot,
    recipient_telegram_id: int,
    actual_recipient_telegram_id: int,
    message: str,
    photo_path: str | None,
    incident_id: int,
    redirect_mode: str,
    reply_markup=None,
) -> None:
    try:
        if photo_path:
            with open(photo_path, "rb") as f:
                await bot.send_photo(
                    chat_id=actual_recipient_telegram_id,
                    photo=f,
                    caption=message,
                    reply_markup=reply_markup,
                )
        else:
            await bot.send_message(
                chat_id=actual_recipient_telegram_id,
                text=message,
                reply_markup=reply_markup,
            )
        storage.save_notification(
            incident_id=incident_id,
            recipient_telegram_id=recipient_telegram_id,
            recipient_actual_telegram_id=actual_recipient_telegram_id,
            redirect_mode=redirect_mode,
            status="sent",
        )
        storage.save_event(
            incident_id=incident_id,
            actor_telegram_id=0,
            actor_name="sistema",
            action="notification_sent",
            success=True,
            extra={
                "recipient": recipient_telegram_id,
                "actual_recipient": actual_recipient_telegram_id,
                "redirect_mode": redirect_mode,
            },
        )
    except Exception as e:
        storage.save_notification(
            incident_id=incident_id,
            recipient_telegram_id=recipient_telegram_id,
            recipient_actual_telegram_id=actual_recipient_telegram_id,
            redirect_mode=redirect_mode,
            status="failed",
            error_message=str(e),
        )
        storage.save_event(
            incident_id=incident_id,
            actor_telegram_id=0,
            actor_name="sistema",
            action="notification_failed",
            success=False,
            reason=str(e),
            extra={"recipient": recipient_telegram_id},
        )


async def notify_incident(
    bot,
    incident: dict,
    employees: dict,
    reporter_employee: dict,
) -> None:
    if incident.get("tipo") != "INCIDENCIA":
        return

    incident_id = incident["id"]
    display_id = storage.generate_display_id("INCIDENCIA", incident_id)
    redirect_mode = settings.NOTIFICATION_REDIRECT_MODE
    is_redirect = redirect_mode == "admin"

    recipient_ids = permissions.get_notification_recipients(incident, employees)

    for tid in recipient_ids:
        emp = employees.get(tid)
        if not emp:
            continue

        rol = emp.get("rol", "EMPLEADO")

        if rol == "GERENTE_GENERAL":
            prefs = storage.get_notification_preferences(tid)
            if not _should_notify_gerente(incident, prefs):
                continue

        actual_tid = settings.ADMIN_TELEGRAM_ID if is_redirect else tid
        recipient_name = emp.get("nombre", "")

        msg, keyboard = format_notification_message(
            incident=incident,
            reporter=reporter_employee,
            incident_id_display=display_id,
            is_redirect=is_redirect,
            actual_recipient_name=recipient_name if is_redirect else None,
            actual_recipient_telegram_id=tid,
        )

        await send_notification_with_logging(
            bot=bot,
            recipient_telegram_id=tid,
            actual_recipient_telegram_id=actual_tid,
            message=msg,
            photo_path=incident.get("photo_path"),
            incident_id=incident_id,
            redirect_mode=redirect_mode,
            reply_markup=keyboard,
        )


async def notify_employee_state_change(
    bot,
    incident: dict,
    new_state: str,
    actor_name: str,
    employees: dict,
) -> None:
    """Notifica al empleado que reportó la incidencia sobre el cambio de estado."""
    from handlers import build_timeline_text, calculate_total_time

    reporter_name = incident.get("employee_name", "")
    display_id = storage.generate_display_id("INCIDENCIA", incident["id"])
    descripcion = incident.get("descripcion", "")
    ubicacion = incident.get("ubicacion", "")
    short_desc = descripcion[:30] + "…" if len(descripcion) > 30 else descripcion

    reporter_first = reporter_name.split()[0] if reporter_name else "empleado"

    if new_state == "ASIGNADA":
        text = f"📬 {actor_name} se está ocupando de tu reporte {display_id} ({short_desc}, {ubicacion})."
    elif new_state == "EN_PROCESO":
        text = f"📬 {actor_name} está resolviendo tu reporte {display_id}."
    elif new_state == "CERRADA":
        events = storage.get_events_for_incident(incident["id"])
        total_time = calculate_total_time(events)
        timeline = build_timeline_text(events)
        header = f"📬 ✅ Tu reporte {display_id} fue resuelto."
        parts = [header]
        if total_time:
            parts.append(f"\n⏱️ Tiempo total: {total_time}")
        if timeline:
            parts.append(f"📊 Historial:\n{timeline}")
        parts.append(f"\nGracias por reportarlo, {reporter_first}.")
        text = "\n".join(parts)
    else:
        return

    # Find reporter's telegram_id by name
    reporter_tid = None
    for tid, emp in employees.items():
        if emp.get("nombre") == reporter_name:
            reporter_tid = tid
            break

    if not reporter_tid:
        return

    redirect_mode = settings.NOTIFICATION_REDIRECT_MODE
    is_redirect = redirect_mode == "admin"
    actual_tid = settings.ADMIN_TELEGRAM_ID if is_redirect else reporter_tid

    try:
        await bot.send_message(chat_id=actual_tid, text=text)
    except Exception:
        pass
