"""Retrospective shift report: consolidation, formatting, and manager notification."""

from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import storage
from config import settings
from config.enums import IncidentState, ReportType, NotificationMode, Role


def consolidate_recent_classifications(employee_name: str, hours: int) -> list[dict]:
    """Returns already-classified items for employee in the last N hours, excluding items in a report."""
    return storage.get_classifications_for_employee_recent(employee_name, hours, exclude_in_report=True)


_CONFIRM_KEYBOARD = InlineKeyboardMarkup([[
    InlineKeyboardButton("✅ Todo bien — cerrar REP", callback_data="report_confirm_all"),
    InlineKeyboardButton("✏️ Corregir un ítem", callback_data="report_correct"),
]])


def format_report_summary(items: list[dict], employee: dict, hours: int) -> tuple[str, InlineKeyboardMarkup]:
    """Formats the retrospective summary for the employee.

    items: list of classification dicts from DB (already saved, have id/tipo/estado).
    Returns (message_text, keyboard).
    """
    employee_name = employee.get("nombre", "")
    incidencias = [i for i in items if i.get("tipo") == ReportType.INCIDENCIA]
    guest_intel = [i for i in items if i.get("tipo") == ReportType.GUEST_INTEL]
    observaciones = [i for i in items if i.get("tipo") == ReportType.OBSERVACION]
    total = len(items)

    lines = [f"📋 Resumen últimas {hours}h — {employee_name}", f"{total} ítem{'s' if total != 1 else ''}", ""]

    num = 1

    if incidencias:
        lines.append(f"🔧 Incidencias ({len(incidencias)}) — ya notificadas")
        for item in incidencias:
            ubicacion = item.get("ubicacion", "")
            descripcion = (item.get("descripcion") or "")[:50]
            estado = item.get("estado") or IncidentState.ABIERTA
            lines.append(f"  {num}. {ubicacion} — {descripcion} [{estado}]")
            num += 1

    if guest_intel:
        lines.append(f"\n👤 Notas de huéspedes ({len(guest_intel)})")
        for item in guest_intel:
            descripcion = (item.get("descripcion") or "")[:50]
            lines.append(f"  {num}. {descripcion}")
            num += 1

    if observaciones:
        lines.append(f"\n📊 Observaciones ({len(observaciones)})")
        for item in observaciones:
            descripcion = (item.get("descripcion") or "")[:50]
            lines.append(f"  {num}. {descripcion}")
            num += 1

    return "\n".join(lines), _CONFIRM_KEYBOARD


def format_report_for_manager(report: dict, items: list[dict], display_id: str) -> str:
    """Formats the manager notification for a closed report.

    items: list of classification dicts linked to the report.
    """
    employee_name = report.get("employee_name", "")
    n_inc = sum(1 for i in items if i.get("tipo") == ReportType.INCIDENCIA)
    n_gi = sum(1 for i in items if i.get("tipo") == ReportType.GUEST_INTEL)
    n_obs = sum(1 for i in items if i.get("tipo") == ReportType.OBSERVACION)
    total = len(items)

    lines = [
        f"📋 Nuevo reporte de turno — {display_id}",
        f"{employee_name} · {total} ítem{'s' if total != 1 else ''} registrados",
        "",
    ]
    if n_inc:
        lines.append(f"🔧 {n_inc} incidencia{'s' if n_inc != 1 else ''}")
    if n_gi:
        lines.append(f"👤 {n_gi} nota{'s' if n_gi != 1 else ''} de huéspedes")
    if n_obs:
        lines.append(f"📊 {n_obs} observación{'es' if n_obs != 1 else ''}")
    lines.append(f"\nVer detalle: /reporte {display_id}")
    return "\n".join(lines)


async def notify_manager_report(bot, report: dict, items: list[dict], employees: dict) -> None:
    """Sends report summary to managers whose mode is 'todo', respecting redirect."""
    report_id = report["id"]
    display_id = storage.generate_display_id(ReportType.REPORT, report_id)
    msg = format_report_for_manager(report, items, display_id)

    redirect_mode = settings.NOTIFICATION_REDIRECT_MODE
    is_redirect = redirect_mode == "admin"

    for tid, emp in employees.items():
        if emp.get("rol") != Role.GERENTE_GENERAL:
            continue
        prefs = storage.get_notification_preferences(tid)
        if prefs.get("mode") != NotificationMode.TODO:
            continue
        actual_tid = settings.ADMIN_TELEGRAM_ID if is_redirect else tid
        try:
            await bot.send_message(chat_id=actual_tid, text=msg)
        except Exception:
            pass
