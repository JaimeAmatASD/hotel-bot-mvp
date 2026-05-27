"""Incident list and room view formatters."""
import storage
from config.enums import IncidentState, ReportType
from permissions import _incident_department
from presenters.format_relative import format_relative_time, format_priority_emoji


def _resolve_assignee_name(incident: dict, employees: dict) -> str | None:
    tid = incident.get("assigned_to_telegram_id")
    if not tid:
        return None
    emp = employees.get(int(tid))
    return emp.get("nombre", "").split()[0] if emp else None


def format_incident_line(incident: dict, employees: dict) -> str:
    iid = incident.get("id", 0)
    display_id = storage.generate_display_id(ReportType.INCIDENCIA, iid)
    prioridad = incident.get("prioridad", "")
    emoji = format_priority_emoji(prioridad)
    ubicacion = incident.get("ubicacion", "")
    descripcion = incident.get("descripcion", "")
    created_at = incident.get("timestamp", "")
    dept = _incident_department(incident)
    estado = incident.get("estado") or IncidentState.ABIERTA

    assignee = _resolve_assignee_name(incident, employees)
    assigned_at = incident.get("assigned_at")

    if estado == IncidentState.ASIGNADA and assignee:
        age = f" {format_relative_time(assigned_at)}" if assigned_at else ""
        estado_str = f"ASIGNADA a {assignee}{age}"
    elif estado == IncidentState.EN_PROCESO and assignee:
        age = f" {format_relative_time(assigned_at)}" if assigned_at else ""
        estado_str = f"EN_PROCESO por {assignee}{age}"
    else:
        estado_str = estado

    time_str = format_relative_time(created_at) if created_at else ""
    line1 = f"{emoji} {display_id} — {prioridad} — {ubicacion} — {descripcion}"
    line2 = f"   {dept} · Reportada {time_str} · {estado_str}"
    return f"{line1}\n{line2}"


def format_incident_list(incidents: list[dict], employees: dict) -> str:
    if not incidents:
        return "✅ No hay incidencias abiertas. Buen momento para un café."
    total = len(incidents)
    shown = incidents[:10]
    lines = [f"🔓 {total} incidencia{'s' if total != 1 else ''} abierta{'s' if total != 1 else ''}"]
    lines.append("")
    for inc in shown:
        lines.append(format_incident_line(inc, employees))
        lines.append("")
    if total > 10:
        lines.append(f"... y {total - 10} más. Filtrá por departamento o prioridad para ver menos.")
        lines.append("")
    lines.append("Mostrá los detalles con: /hab N")
    return "\n".join(lines)


def format_room_view(
    room: str,
    incidents_open: list[dict],
    incidents_closed: list[dict],
    guest_intel: list[dict],
    observations: list[dict],
    employees: dict,
) -> str:
    lines = [f"🛏️ {room}", ""]

    if incidents_open:
        lines.append(f"🔴 Incidencias abiertas ({len(incidents_open)}):")
        for inc in incidents_open:
            lines.append(format_incident_line(inc, employees))
    else:
        lines.append("🔴 Incidencias abiertas (0): ninguna")

    lines.append("")

    if incidents_closed:
        lines.append(f"✅ Incidencias resueltas recientes ({len(incidents_closed)}):")
        for inc in incidents_closed:
            iid = inc.get("id", 0)
            display_id = storage.generate_display_id(ReportType.INCIDENCIA, iid)
            prioridad = inc.get("prioridad", "")
            emoji = format_priority_emoji(prioridad)
            descripcion = inc.get("descripcion", "")
            res_min = inc.get("resolution_time_minutes")
            closed_at = inc.get("closed_at", "")
            time_str = format_relative_time(closed_at) if closed_at else ""
            res_str = f"resuelta en {res_min} min" if res_min is not None else "resuelta"
            lines.append(f"{emoji} {display_id} — {descripcion} ({res_str}, {time_str})")
    else:
        lines.append("✅ Incidencias resueltas recientes (0): ninguna")

    lines.append("")

    if guest_intel:
        lines.append(f"👤 Memoria del huésped ({len(guest_intel)}):")
        for gi in guest_intel:
            categoria = gi.get("categoria", "")
            descripcion = gi.get("descripcion", "") or gi.get("message", "")
            reporter = gi.get("employee_name", "")
            created = gi.get("timestamp", "")
            time_str = format_relative_time(created) if created else ""
            lines.append(f"{categoria} — {descripcion} ({reporter}, {time_str})")
    else:
        lines.append("👤 Memoria del huésped (0): ninguna")

    lines.append("")

    if observations:
        lines.append(f"📋 Observaciones ({len(observations)}):")
        for obs in observations:
            descripcion = obs.get("descripcion", "") or obs.get("message", "")
            reporter = obs.get("employee_name", "")
            created = obs.get("timestamp", "")
            time_str = format_relative_time(created) if created else ""
            lines.append(f"• {descripcion} ({reporter}, {time_str})")
    else:
        lines.append("📋 Observaciones (0): ninguna")

    return "\n".join(lines)
