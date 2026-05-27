"""Event timeline and incident history formatters."""
from datetime import datetime
import storage
from config.enums import ReportType
from presenters.constants import ACTION_EMOJI, ACTION_LABELS
from presenters.format_relative import format_relative_time, format_priority_emoji


def calculate_total_time(events: list[dict]) -> str:
    created_ts = next((e["timestamp"] for e in events if e["action"] == "created"), None)
    closed_ts = next((e["timestamp"] for e in events if e["action"] == "cerrar" and e["success"]), None)
    if not created_ts or not closed_ts:
        return ""
    try:
        delta_minutes = int((datetime.fromisoformat(closed_ts) - datetime.fromisoformat(created_ts)).total_seconds() / 60)
    except Exception:
        return ""
    if delta_minutes < 1:
        return "menos de 1 min"
    if delta_minutes < 60:
        return f"{delta_minutes} min"
    hours = delta_minutes // 60
    mins = delta_minutes % 60
    return f"{hours}h {mins}min" if mins else f"{hours}h"


def build_timeline_text(events: list[dict]) -> str:
    skip = {"notification_sent", "notification_failed"}
    lines = []
    for e in events:
        action = e.get("action", "")
        if action in skip:
            continue
        actor = e.get("actor_name") or ""
        ts = e.get("timestamp", "")
        time_str = format_relative_time(ts) if ts else ""
        label = ACTION_LABELS.get(action, action)

        if action == "created":
            lines.append(f"   • Reportada {time_str}")
        elif action in ("tomar", "en_proceso", "cerrar"):
            actor_first = actor.split()[0] if actor else "alguien"
            lines.append(f"   • {label} {actor_first} {time_str}")
        elif action == "action_rejected_already_done":
            from_state = e.get("from_state", "?")
            lines.append(f"   • ❌ Intento rechazado ({from_state}) por {actor.split()[0] if actor else '?'} {time_str}")
        elif action == "action_rejected_no_permission":
            lines.append(f"   • ❌ Intento sin permisos por {actor.split()[0] if actor else '?'} {time_str}")
    return "\n".join(lines)


def format_incident_history(incident: dict, events: list[dict]) -> str:
    iid = incident.get("id", 0)
    display_id = storage.generate_display_id(ReportType.INCIDENCIA, iid)
    prioridad = incident.get("prioridad", "")
    ubicacion = incident.get("ubicacion", "")
    descripcion = incident.get("descripcion", "")

    lines = [f"📋 Historial {display_id}", ""]
    lines.append(f"{format_priority_emoji(prioridad)} {prioridad} — {ubicacion}")
    lines.append(f"📝 {descripcion}")
    lines.append("")

    total_time = calculate_total_time(events)

    for e in events:
        action = e.get("action", "")
        actor = e.get("actor_name") or "sistema"
        actor_first = actor.split()[0] if actor != "sistema" else "sistema"
        ts = e.get("timestamp", "")
        time_label = ts[11:16] if len(ts) >= 16 else ts  # HH:MM
        emoji = ACTION_EMOJI.get(action, "•")
        from_s = e.get("from_state") or ""
        to_s = e.get("to_state") or ""

        if action == "created":
            lines.append(f"{emoji} {time_label} — {descripcion[:50]}")
            lines.append(f"   Creada por {actor}")
        elif action in ("tomar", "en_proceso", "cerrar"):
            label = ACTION_LABELS.get(action, action)
            lines.append(f"{emoji} {time_label} — {label} {actor_first}")
            if from_s and to_s:
                lines.append(f"   {from_s} → {to_s}")
            if action == "cerrar" and total_time:
                lines.append(f"   Tiempo total: {total_time}")
        elif action == "notification_sent":
            extra = e.get("extra") or {}
            if isinstance(extra, dict):
                recipient = extra.get("recipient", "?")
            else:
                recipient = "?"
            lines.append(f"🔔 {time_label} — Notificación enviada (destinatario {recipient})")
        elif action == "notification_failed":
            lines.append(f"🔕 {time_label} — Notificación fallida: {e.get('reason', '')}")
        elif action in ("action_rejected_already_done", "action_rejected_no_permission"):
            reason = e.get("reason") or ""
            lines.append(f"❌ {time_label} — {actor_first} intentó actuar (rechazado)")
            if reason:
                lines.append(f"   Razón: {reason}")
        lines.append("")

    return "\n".join(lines).rstrip()
