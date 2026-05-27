"""Orchestrates notification dispatch: filter recipients, format, send in parallel."""
import asyncio

import storage
import permissions
from config import settings
from config.enums import ReportType, Role

from notifier.filters import should_notify_gerente
from notifier.format import format_notification_message
from notifier.send import send_notification_with_logging


async def _notify_one_recipient(
    bot, incident, reporter_employee, employees, tid,
    redirect_mode, is_redirect, display_id, incident_id,
):
    emp = employees.get(tid)
    if not emp:
        return

    rol = emp.get("rol", Role.EMPLEADO)
    if rol == Role.GERENTE_GENERAL:
        prefs = storage.get_notification_preferences(tid)
        if not should_notify_gerente(incident, prefs):
            return

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


async def notify_incident(bot, incident: dict, employees: dict, reporter_employee: dict) -> None:
    if incident.get("tipo") != ReportType.INCIDENCIA:
        return

    incident_id = incident["id"]
    display_id = storage.generate_display_id(ReportType.INCIDENCIA, incident_id)
    redirect_mode = settings.NOTIFICATION_REDIRECT_MODE
    is_redirect = redirect_mode == "admin"

    recipient_ids = permissions.get_notification_recipients(incident, employees)

    await asyncio.gather(
        *[_notify_one_recipient(bot, incident, reporter_employee, employees, tid,
                                redirect_mode, is_redirect, display_id, incident_id)
          for tid in recipient_ids],
        return_exceptions=True,
    )
