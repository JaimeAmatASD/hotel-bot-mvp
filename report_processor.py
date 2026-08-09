"""Retrospective shift report: consolidation, formatting, and manager notification."""

from datetime import datetime
from telegram import InlineKeyboardMarkup

import storage
import permissions
from config import settings
from config.enums import IncidentState, ReportType, NotificationMode, Role
from notifier.sender import as_sender
from presenters.constants import ESTADO_EMOJI
from presenters.format_location import shorten_room_label
from presenters.keyboards import REPORT_DRAFT_KEYBOARD

_DIVIDER = "──────────────────────────"
_TERMINAL_STATES = {IncidentState.CERRADA, IncidentState.CANCELADA}
_MAX_DESC = 60
# Con 13 pendientes arrastradas, el informe de hoy queda sepultado. Se muestran las
# más viejas y el resto va como contador; /abiertas tiene la lista completa.
_MAX_CARRYOVER = 5


def _value(item: dict, key: str) -> str:
    return str(item.get(key) or "").strip()


def _truncate(texto: str, limite: int = _MAX_DESC) -> str:
    """Colapsa espacios y corta. Un informe de 15 ítems sin esto no se lee en el celular."""
    texto = " ".join(texto.split())
    return texto if len(texto) <= limite else texto[:limite - 1].rstrip() + "…"


def _pendiente_line(item: dict, *, arrastre: bool = False) -> str:
    """Línea de pendiente, con ID accionable y marca ↩ si viene arrastrada de otro día.

    El arrastre lo dice quien llama, no se deduce comparando fechas: con cero ítems
    cargados hoy no habría contra qué comparar.
    """
    estado = item.get("estado") or IncidentState.NUEVA
    ubic = shorten_room_label(_value(item, "ubicacion")) or "Sin ubicación"
    desc = _truncate(_value(item, "descripcion") or "Sin descripción")
    prio = _value(item, "prioridad")
    prio_part = f" · {prio}" if prio else ""
    did = storage.generate_display_id(ReportType.INCIDENCIA, item.get("id", 0))
    marca = ""
    if arrastre:
        ts = _value(item, "timestamp")
        try:
            marca = f" · ↩ {datetime.fromisoformat(ts).strftime('%d/%m')}"
        except ValueError:
            marca = " · ↩"
    return (f"• {did} · {ubic} — {desc}{prio_part} · "
            f"{ESTADO_EMOJI.get(estado, '')} {estado}{marca}")


def _guest_context(item: dict) -> str:
    parts = []
    if item.get("huesped_afectado"):
        parts.append("huésped afectado")
    habitacion = _value(item, "habitacion_huesped")
    if habitacion:
        parts.append(f"huésped hab {habitacion}")
    nota = _value(item, "tipo_nota_huesped")
    if nota:
        parts.append(nota.lower())
    return f" · {' · '.join(parts)}" if parts else ""


def _incident_line(prefix: str, item: dict) -> str:
    estado = item.get("estado") or IncidentState.NUEVA
    em = ESTADO_EMOJI.get(estado, "")
    ubic = shorten_room_label(_value(item, "ubicacion")) or "Sin ubicación"
    desc = _truncate(_value(item, "descripcion") or "Sin descripción")
    prio = _value(item, "prioridad")
    prio_part = f" · {prio}" if prio else ""
    return f"{prefix} {ubic} — {desc}{prio_part} · {em} {estado}{_guest_context(item)}"


def _guest_line(prefix: str, item: dict) -> str:
    ubic = shorten_room_label(_value(item, "ubicacion"))
    desc = _truncate(_value(item, "descripcion") or "Sin descripción")
    prefix_text = f"{ubic} — " if ubic else ""
    return f"{prefix} {prefix_text}{desc}{_guest_context(item)}"


def _observation_line(prefix: str, item: dict) -> str:
    ubic = shorten_room_label(_value(item, "ubicacion"))
    desc = _truncate(_value(item, "descripcion") or "Sin descripción")
    prefix_text = f"{ubic} — " if ubic else ""
    return f"{prefix} {prefix_text}{desc}"


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


def _render_item_sections(items: list[dict]) -> tuple[list[str], list[dict]]:
    """Devuelve (líneas de secciones numeradas, incidencias abiertas). Compartido
    por el informe per-persona y el rollup de sector."""
    incidencias = [i for i in items if i.get("tipo") == ReportType.INCIDENCIA]
    guest = [i for i in items if i.get("tipo") == ReportType.GUEST_INTEL]
    obs = [i for i in items if i.get("tipo") == ReportType.OBSERVACION]

    lines: list[str] = []
    num = 1
    if incidencias:
        lines.append(f"🔧 INCIDENCIAS ({len(incidencias)})")
        for it in incidencias:
            lines.append(_incident_line(f"{num}.", it))
            num += 1
    if guest:
        lines.append(f"👤 NOTAS DE HUÉSPED ({len(guest)})")
        for it in guest:
            lines.append(_guest_line(f"{num}.", it))
            num += 1
    if obs:
        lines.append(f"📝 NOVEDADES DEL TURNO ({len(obs)})")
        for it in obs:
            lines.append(_observation_line(f"{num}.", it))
            num += 1

    pendientes = [i for i in incidencias
                  if (i.get("estado") or IncidentState.NUEVA) not in _TERMINAL_STATES]
    return lines, pendientes


def render_shift_report(items: list[dict], *, display_id: str, employee_name: str,
                        department: str | None, carryover: list[dict] | tuple = (),
                        closed_at: str | None = None) -> str:
    """Plantilla única del informe de turno. Reutilizada por el resumen previo,
    la notificación al manager y /reporte REP-N.

    `carryover` son incidencias abiertas de días anteriores: se muestran entre los
    pendientes pero no cuentan como ítems del día ni se linkean al informe.
    """
    total = len(items)

    rng = _time_range(items)
    meta = f"{rng} · " if rng else ""
    header2 = f"👤 {employee_name}" + (f" · {department}" if department else "")
    lines = [
        f"📋 INFORME DE TURNO — {display_id}",
        header2,
        f"🕐 {meta}{total} ítem{'s' if total != 1 else ''}",
    ]

    section_lines, pendientes_hoy = _render_item_sections(items)
    # El arrastre va primero dentro de los pendientes: son los que llevan más tiempo.
    pendientes = [(it, True) for it in carryover] + [(it, False) for it in pendientes_hoy]
    if pendientes:
        lines.append("")
        lines.append(f"⚠️ QUEDA PENDIENTE ({len(pendientes)})")
        for it, es_arrastre in pendientes[:_MAX_CARRYOVER]:
            lines.append(_pendiente_line(it, arrastre=es_arrastre))
        ocultas = len(pendientes) - _MAX_CARRYOVER
        if ocultas > 0:
            lines.append(f"…y {ocultas} más abiertas · /abiertas para verlas")

    lines.append(_DIVIDER)
    lines.extend(section_lines or ["Sin ítems cargados hoy."])
    lines.append(_DIVIDER)

    if closed_at:
        try:
            ct = datetime.fromisoformat(closed_at).strftime("%H:%M")
            lines.append(f"Cerrado {ct} · /reporte {display_id}")
        except ValueError:
            lines.append(f"/reporte {display_id}")
    return "\n".join(lines)


def sector_items(department: str, hours: int) -> list[dict]:
    """Ítems del sector en la ventana (read-only). Incidencias por categoría→depto;
    observaciones/notas de huésped por el depto del que reportó."""
    dept = department.upper()
    out = []
    for it in storage.get_classifications_recent(hours):
        if it.get("tipo") == ReportType.INCIDENCIA:
            item_dept = permissions._incident_department(it)
        else:
            item_dept = it.get("employee_dept") or ""
        if item_dept.upper() == dept:
            out.append(it)
    return out


def render_sector_rollup(items: list[dict], *, department: str, hours: int) -> str:
    """Vista read-only del estado del sector en la ventana. No es un REP."""
    total = len(items)
    rng = _time_range(items)
    meta = f"{rng} · " if rng else ""
    lines = [
        f"📋 ESTADO DEL SECTOR — {department}",
        f"🕐 {meta}{total} ítem{'s' if total != 1 else ''} · últimas {hours}h",
        _DIVIDER,
    ]
    section_lines, abiertas = _render_item_sections(items)
    if not section_lines:
        lines.append("Sin actividad en la ventana.")
    lines.extend(section_lines)
    if abiertas:
        lines.append("⏳ ABIERTAS EN EL SECTOR")
        for it in abiertas:
            lines.append(_incident_line("•", it))
    lines.append(_DIVIDER)
    return "\n".join(lines)


def consolidate_recent_classifications(employee_name: str, hours: int) -> list[dict]:
    """Returns already-classified items for employee in the last N hours, excluding items in a report."""
    return storage.get_classifications_for_employee_recent(employee_name, hours, exclude_in_report=True)




def format_report_summary(items: list[dict], employee: dict,
                          carryover: list[dict] | tuple = ()) -> tuple[str, InlineKeyboardMarkup]:
    """Borrador previo a confirmar, con la plantilla del informe (display_id borrador).

    items: clasificaciones del día ya guardadas (tienen id/tipo/estado).
    carryover: incidencias abiertas de días anteriores, solo para mostrar.
    """
    text = render_shift_report(
        items, display_id="(borrador)",
        employee_name=employee.get("nombre", ""),
        department=employee.get("departamento"),
        carryover=carryover,
    )
    text += "\n\n¿Sumás algo más o lo cerramos?"
    return text, REPORT_DRAFT_KEYBOARD


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
            if not settings.REPORT_NOTIFY_GERENTE:
                continue
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
