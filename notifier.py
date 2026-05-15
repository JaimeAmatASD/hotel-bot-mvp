import storage
import permissions
from config import settings
from handlers import PRIORIDAD_EMOJI, TIPO_EMOJI


def format_notification_message(
    incident: dict,
    reporter: dict,
    incident_id_display: str,
    is_redirect: bool = False,
    actual_recipient_name: str | None = None,
) -> str:
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

    lines = [
        f"🔔 Nueva incidencia — {incident_id_display}",
        f"{tipo_emoji} {cat_str} — {prioridad_emoji} {prioridad}",
        f"📍 {ubicacion}",
        f"📝 {descripcion}",
        "",
        f"Reportado por: {reporter_name} ({reporter_dept})",
    ]
    body = "\n".join(lines)

    if is_redirect and actual_recipient_name:
        prefix = f"🧪 [Modo testing — destinatario real: {actual_recipient_name}]\n\n"
        return prefix + body
    return body


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
) -> None:
    try:
        if photo_path:
            with open(photo_path, "rb") as f:
                await bot.send_photo(
                    chat_id=actual_recipient_telegram_id,
                    photo=f,
                    caption=message,
                )
        else:
            await bot.send_message(
                chat_id=actual_recipient_telegram_id,
                text=message,
            )
        storage.save_notification(
            incident_id=incident_id,
            recipient_telegram_id=recipient_telegram_id,
            recipient_actual_telegram_id=actual_recipient_telegram_id,
            redirect_mode=redirect_mode,
            status="sent",
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

        msg = format_notification_message(
            incident=incident,
            reporter=reporter_employee,
            incident_id_display=display_id,
            is_redirect=is_redirect,
            actual_recipient_name=recipient_name if is_redirect else None,
        )

        await send_notification_with_logging(
            bot=bot,
            recipient_telegram_id=tid,
            actual_recipient_telegram_id=actual_tid,
            message=msg,
            photo_path=incident.get("photo_path"),
            incident_id=incident_id,
            redirect_mode=redirect_mode,
        )
