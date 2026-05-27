"""Pure formatting helpers — no I/O, no async."""
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config.enums import IncidentState, ReportType
from presenters.constants import PRIORIDAD_EMOJI, TIPO_EMOJI


def _time_ago(dt_str: str) -> str:
    try:
        dt = datetime.fromisoformat(dt_str)
        minutes = int((datetime.now() - dt).total_seconds() / 60)
        if minutes < 1:
            return "ahora mismo"
        return f"{minutes} min"
    except Exception:
        return "?"


def build_keyboard_for_state(incident_id: int, estado: str) -> InlineKeyboardMarkup | None:
    cb = lambda action: f"incident_action:{incident_id}:{action}"
    buttons_by_state = {
        IncidentState.ABIERTA:    [("🙋 Tomar", cb("tomar")), ("⏳ En proceso", cb("proceso")), ("✅ Cerrar", cb("cerrar"))],
        IncidentState.ASIGNADA:   [("⏳ En proceso", cb("proceso")), ("✅ Cerrar", cb("cerrar"))],
        IncidentState.EN_PROCESO: [("✅ Cerrar", cb("cerrar"))],
        IncidentState.CERRADA:    [],
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
    estado = incident.get("estado", IncidentState.ABIERTA)
    prioridad = incident.get("prioridad", "")
    categoria = incident.get("categoria", "")
    subcategoria = incident.get("subcategoria")
    ubicacion = incident.get("ubicacion", "")
    descripcion = incident.get("descripcion", "")
    reporter_name = reporter.get("nombre", "")
    reporter_dept = reporter.get("departamento", "")

    cat_str = f"{categoria} › {subcategoria}" if subcategoria else categoria
    prioridad_emoji = PRIORIDAD_EMOJI.get(prioridad, "")
    tipo_emoji = TIPO_EMOJI.get(ReportType.INCIDENCIA, "🔧")

    if estado == IncidentState.ABIERTA:
        header = f"🔔 Nueva incidencia — {incident_id_display}"
    elif estado == IncidentState.ASIGNADA:
        assignee_name = incident.get("_assignee_name", f"ID {incident.get('assigned_to_telegram_id', '?')}")
        header = f"🔔 {incident_id_display} — ASIGNADA a {assignee_name}"
    elif estado == IncidentState.EN_PROCESO:
        header = f"🔔 {incident_id_display} — EN PROCESO"
    elif estado == IncidentState.CERRADA:
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

    if estado == IncidentState.ABIERTA:
        created_at = incident.get("timestamp")
        if created_at:
            lines.append(f"Hace: {_time_ago(created_at)}")
    elif estado in (IncidentState.ASIGNADA, IncidentState.EN_PROCESO):
        created_at = incident.get("timestamp")
        if created_at:
            lines.append(f"Hace: {_time_ago(created_at)}")
        assigned_at = incident.get("assigned_at")
        if assigned_at:
            lines.append(f"Asignado: hace {_time_ago(assigned_at)}")
    elif estado == IncidentState.CERRADA:
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
