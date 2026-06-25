"""Notify the original reporter when their incident changes state."""
import storage
from config import settings
from config.enums import IncidentState, ReportType
from presenters import build_timeline_text, calculate_total_time
from notifier.format import build_keyboard_for_state
from notifier.sender import as_sender


async def notify_employee_state_change(
    bot,
    incident: dict,
    new_state: str,
    actor_name: str,
    employees: dict,
) -> None:
    reporter_name = incident.get("employee_name", "")
    display_id = storage.generate_display_id(ReportType.INCIDENCIA, incident["id"])
    descripcion = incident.get("descripcion", "")
    ubicacion = incident.get("ubicacion", "")
    short_desc = descripcion[:30] + "…" if len(descripcion) > 30 else descripcion

    reporter_first = reporter_name.split()[0] if reporter_name else "empleado"

    if new_state == IncidentState.ASIGNADA:
        text = f"📬 {actor_name} se está ocupando de tu reporte {display_id} ({short_desc}, {ubicacion})."
    elif new_state == IncidentState.EN_PROCESO:
        text = f"📬 {actor_name} está resolviendo tu reporte {display_id}."
    elif new_state == IncidentState.RESUELTA:
        text = f"📬 {actor_name} marcó como resuelto tu reporte {display_id}. Pendiente de validación final."
    elif new_state == IncidentState.CERRADA:
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

    sender = as_sender(bot)
    try:
        await sender.send_text(chat_id=actual_tid, text=text)
    except Exception:
        pass


import asyncio
import permissions


def _resolve_recipient(tid: int):
    """Aplica redirect de testing."""
    is_redirect = settings.NOTIFICATION_REDIRECT_MODE == "admin"
    return settings.ADMIN_TELEGRAM_ID if is_redirect else tid


async def notify_assignee(bot, incident: dict, employees: dict) -> None:
    """Avisa a la persona recién asignada que tiene una tarea nueva."""
    tid = incident.get("assigned_to_telegram_id")
    if not tid:
        return
    tid = int(tid)
    display_id = storage.generate_display_id(ReportType.INCIDENCIA, incident["id"])
    desc = incident.get("descripcion", "")
    ubic = incident.get("ubicacion", "")
    text = f"🔔 Nueva tarea asignada — {display_id}\n🔧 {desc}\n📍 {ubic}\nCuando puedas, marcá tu avance acá abajo 👇"
    keyboard = build_keyboard_for_state(incident["id"], IncidentState.ASIGNADA)
    sender = as_sender(bot)
    try:
        await sender.send_text(chat_id=_resolve_recipient(tid), text=text, reply_markup=keyboard)
    except Exception:
        pass


async def notify_managers_resolved(bot, incident: dict, actor_name: str, employees: dict) -> None:
    """Avisa a los managers del depto que la incidencia fue marcada como resuelta (a validar)."""
    display_id = storage.generate_display_id(ReportType.INCIDENCIA, incident["id"])
    desc = incident.get("descripcion", "")
    text = f"✅ {actor_name} marcó como resuelto {display_id} ({desc}). Validá y cerrá cuando confirmes."
    recipients = permissions.get_notification_recipients(incident, employees)
    sender = as_sender(bot)

    async def _send(tid):
        try:
            await sender.send_text(chat_id=_resolve_recipient(tid), text=text)
        except Exception:
            pass

    await asyncio.gather(*(_send(t) for t in recipients), return_exceptions=True)
