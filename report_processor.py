"""Retrospective shift report: consolidation, formatting, and manager notification."""

from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import storage
from config import settings
from config.enums import IncidentState, ReportType, NotificationMode, Role
from notifier.sender import as_sender
from presenters.constants import ESTADO_EMOJI

_DIVIDER = "──────────────────────────"
_TERMINAL_STATES = {IncidentState.CERRADA, IncidentState.CANCELADA}


def _time_range(items: list[dict]) -> str:
    """'25/06 · 08:10–15:45' a partir de los timestamps de los ítems."""
    stamps = sorted(i.get("timestamp", "") for i in items if i.get("timestamp"))
    if not stamps:
        return ""
    try:
        first = datetime.fromisoformat(stamps[0])
        last = datetime.fromisoformat(stamps[-1])
    except ValueError:
        return ""
    return f"{first.strftime('%d/%m')} · {first.strftime('%H:%M')}–{last.strftime('%H:%M')}"


def render_shift_report(items: list[dict], *, display_id: str, employee_name: str,
                        department: str | None, closed_at: str | None = None) -> str:
    """Plantilla única del informe de turno. Reutilizada por el resumen previo,
    la notificación al manager y /reporte REP-N."""
    incidencias = [i for i in items if i.get("tipo") == ReportType.INCIDENCIA]
    guest = [i for i in items if i.get("tipo") == ReportType.GUEST_INTEL]
    obs = [i for i in items if i.get("tipo") == ReportType.OBSERVACION]
    total = len(items)

    rng = _time_range(items)
    meta = f"{rng} · " if rng else ""
    header2 = f"👤 {employee_name}" + (f" · {department}" if department else "")
    lines = [
        f"📋 INFORME DE TURNO — {display_id}",
        header2,
        f"🕐 {meta}{total} ítem{'s' if total != 1 else ''}",
        _DIVIDER,
    ]

    num = 1
    if incidencias:
        lines.append(f"🔧 INCIDENCIAS ({len(incidencias)})")
        for it in incidencias:
            estado = it.get("estado") or IncidentState.NUEVA
            em = ESTADO_EMOJI.get(estado, "")
            ubic = it.get("ubicacion", "") or ""
            desc = it.get("descripcion", "") or ""
            prio = it.get("prioridad", "") or ""
            lines.append(f" {num}. {ubic} — {desc} · {prio} · {em} {estado}".replace("  ", " "))
            num += 1

    if guest:
        lines.append(f"👤 NOTAS DE HUÉSPED ({len(guest)})")
        for it in guest:
            ubic = it.get("ubicacion", "") or ""
            desc = it.get("descripcion", "") or ""
            prefix = f"{ubic} — " if ubic else ""
            lines.append(f" {num}. {prefix}{desc}")
            num += 1

    if obs:
        lines.append(f"📝 NOVEDADES DEL TURNO ({len(obs)})")
        for it in obs:
            lines.append(f" {num}. {it.get('descripcion', '') or ''}")
            num += 1

    pendientes = [i for i in incidencias
                  if (i.get("estado") or IncidentState.NUEVA) not in _TERMINAL_STATES]
    if pendientes:
        lines.append("⏳ QUEDA PENDIENTE PARA EL PRÓXIMO TURNO")
        for it in pendientes:
            ubic = it.get("ubicacion", "") or ""
            desc = it.get("descripcion", "") or ""
            estado = it.get("estado") or IncidentState.NUEVA
            lines.append(f" • {ubic} — {desc} ({estado})")

    lines.append(_DIVIDER)
    if closed_at:
        try:
            ct = datetime.fromisoformat(closed_at).strftime("%H:%M")
            lines.append(f"Cerrado {ct} · /reporte {display_id} para ver")
        except ValueError:
            lines.append(f"/reporte {display_id} para ver")
    return "\n".join(lines)


def consolidate_recent_classifications(employee_name: str, hours: int) -> list[dict]:
    """Returns already-classified items for employee in the last N hours, excluding items in a report."""
    return storage.get_classifications_for_employee_recent(employee_name, hours, exclude_in_report=True)


_CONFIRM_KEYBOARD = InlineKeyboardMarkup([[
    InlineKeyboardButton("✅ Todo bien — cerrar REP", callback_data="report_confirm_all"),
    InlineKeyboardButton("✏️ Corregir un ítem", callback_data="report_correct"),
]])


def format_report_summary(items: list[dict], employee: dict, hours: int) -> tuple[str, InlineKeyboardMarkup]:
    """Resumen previo a confirmar, con la plantilla del informe (display_id borrador).

    items: list of classification dicts from DB (already saved, have id/tipo/estado).
    Returns (message_text, keyboard).
    """
    text = render_shift_report(
        items, display_id="(borrador)",
        employee_name=employee.get("nombre", ""),
        department=employee.get("departamento"),
    )
    text += "\n\nRevisá y confirmá para cerrar el informe del turno."
    return text, _CONFIRM_KEYBOARD


def format_report_for_sheet(items: list[dict]) -> str:
    """One-line plain-text summary of report items for the 'Resumen / link' column."""
    parts = []
    for item in items:
        descripcion = (item.get("descripcion") or "")[:60]
        tipo = item.get("tipo")
        if tipo == ReportType.INCIDENCIA:
            ubicacion = item.get("ubicacion", "")
            estado = item.get("estado") or IncidentState.NUEVA
            parts.append(f"[INC] {ubicacion}: {descripcion} ({estado})")
        elif tipo == ReportType.GUEST_INTEL:
            parts.append(f"[GI] {descripcion}")
        elif tipo == ReportType.OBSERVACION:
            parts.append(f"[OBS] {descripcion}")
    return " | ".join(parts)


def format_report_for_manager(report: dict, items: list[dict], display_id: str) -> str:
    """Notificación al manager de un reporte cerrado, con la plantilla completa."""
    return render_shift_report(
        items, display_id=display_id,
        employee_name=report.get("employee_name", ""),
        department=report.get("employee_department"),
        closed_at=report.get("closed_at"),
    )


async def notify_manager_report(bot, report: dict, items: list[dict], employees: dict) -> None:
    """Envía el informe cerrado al encargado del departamento del autor (siempre) y al
    gerente general (si su modo es 'todo'). No autonotifica al autor. Respeta redirect."""
    report_id = report["id"]
    display_id = storage.generate_display_id(ReportType.REPORT, report_id)
    msg = format_report_for_manager(report, items, display_id)

    author_tid = report.get("employee_telegram_id")
    author_dept = report.get("employee_department")
    is_redirect = settings.NOTIFICATION_REDIRECT_MODE == "admin"

    sender = as_sender(bot)
    seen: set = set()
    for tid, emp in employees.items():
        if tid == author_tid:
            continue
        rol = emp.get("rol")
        if rol == Role.ENCARGADO and emp.get("departamento") == author_dept:
            pass  # el encargado del depto siempre recibe el informe de su equipo
        elif rol == Role.GERENTE_GENERAL:
            if storage.get_notification_preferences(tid).get("mode") != NotificationMode.TODO:
                continue
        else:
            continue
        actual_tid = settings.ADMIN_TELEGRAM_ID if is_redirect else tid
        if actual_tid in seen:
            continue
        seen.add(actual_tid)
        try:
            await sender.send_text(chat_id=actual_tid, text=msg)
        except Exception:
            pass
