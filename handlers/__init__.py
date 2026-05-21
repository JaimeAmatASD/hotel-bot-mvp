from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

PRIORIDAD_EMOJI = {
    "CRITICA": "🔴",
    "ALTA": "🟠",
    "MEDIA": "🟡",
    "BAJA": "🟢",
}

TIPO_EMOJI = {
    "INCIDENCIA": "🔧",
    "OBSERVACION": "👁",
    "GUEST_INTEL": "💡",
    "NO_REPORTE": "ℹ️",
    "ERROR": "❌",
}

CONFIRM_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("✅ Correcto", callback_data="confirm"),
        InlineKeyboardButton("✏️ Corregir", callback_data="correct"),
    ]
])


def format_summary(result: dict) -> str:
    tipo = result.get("tipo", "ERROR")
    prioridad = result.get("prioridad")
    ubicacion = result.get("ubicacion")
    categoria = result.get("categoria")
    subcategoria = result.get("subcategoria")
    descripcion = result.get("descripcion", "")

    tipo_emoji = TIPO_EMOJI.get(tipo, "❓")
    prioridad_str = f" — {PRIORIDAD_EMOJI.get(prioridad, '')} {prioridad}" if prioridad else ""

    lines = [f"<b>{tipo_emoji} {tipo}{prioridad_str}</b>"]
    if ubicacion:
        lines.append(f"📍 {ubicacion}")
    if categoria:
        cat_str = f"{categoria} › {subcategoria}" if subcategoria else categoria
        lines.append(f"🏷 {cat_str}")
    lines.append(f"📝 {descripcion}")

    return "\n".join(lines)


def format_debug_block(result: dict) -> str:
    lines = ["─────────────", "🔍 <b>Detalles técnicos:</b>"]

    confianza = result.get("confianza")
    if confianza is not None:
        lines.append(f"• Confianza: {round(confianza * 100)}%")

    idioma = result.get("idioma_original")
    if idioma:
        lines.append(f"• Idioma original: {idioma}")

    huesped = result.get("huesped_afectado")
    if huesped is not None:
        lines.append(f"• Huésped afectado: {'sí' if huesped else 'no'}")

    hab = result.get("habitacion_huesped")
    if hab:
        lines.append(f"• Habitación huésped: {hab}")

    nota = result.get("tipo_nota_huesped")
    if nota:
        lines.append(f"• Tipo nota huésped: {nota}")

    subcat = result.get("subcategoria")
    if subcat:
        lines.append(f"• Subcategoría: {subcat}")

    campos = result.get("campos_faltantes") or []
    lines.append(f"• Campos faltantes: {', '.join(campos) if campos else 'ninguno'}")

    return "\n".join(lines)


def format_summary_with_warning(result: dict) -> str:
    return format_summary(result) + "\n\n⚠️ <i>Tengo dudas sobre la clasificación, confirmá si está bien.</i>"


def get_employee(update, context):
    tid = update.effective_user.id
    return context.bot_data["employees"].get(tid)


def format_relative_time(timestamp_iso: str) -> str:
    try:
        dt = datetime.fromisoformat(timestamp_iso)
        total_seconds = (datetime.now() - dt).total_seconds()
        minutes = int(total_seconds / 60)
        if minutes < 1:
            return "ahora mismo"
        if minutes < 60:
            return f"hace {minutes} min"
        hours = int(minutes / 60)
        if hours < 24:
            return f"hace {hours} h"
        days = int(hours / 24)
        return f"hace {days} día" if days == 1 else f"hace {days} días"
    except Exception:
        return "?"


def format_priority_emoji(prioridad: str) -> str:
    return PRIORIDAD_EMOJI.get(prioridad, "")


def _resolve_assignee_name(incident: dict, employees: dict) -> str | None:
    tid = incident.get("assigned_to_telegram_id")
    if not tid:
        return None
    emp = employees.get(int(tid))
    return emp.get("nombre", "").split()[0] if emp else None


def format_incident_line(incident: dict, employees: dict) -> str:
    import storage as _storage
    from permissions import _incident_department
    iid = incident.get("id", 0)
    display_id = _storage.generate_display_id("INCIDENCIA", iid)
    prioridad = incident.get("prioridad", "")
    emoji = format_priority_emoji(prioridad)
    ubicacion = incident.get("ubicacion", "")
    descripcion = incident.get("descripcion", "")
    created_at = incident.get("timestamp", "")
    dept = _incident_department(incident)
    estado = incident.get("estado") or "ABIERTA"

    assignee = _resolve_assignee_name(incident, employees)
    assigned_at = incident.get("assigned_at")

    if estado == "ASIGNADA" and assignee:
        age = f" {format_relative_time(assigned_at)}" if assigned_at else ""
        estado_str = f"ASIGNADA a {assignee}{age}"
    elif estado == "EN_PROCESO" and assignee:
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
    import storage as _storage
    lines = [f"🛏️ {room}"]
    lines.append("")

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
            display_id = _storage.generate_display_id("INCIDENCIA", iid)
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


def get_help_text(role: str, department: str | None = None) -> str:
    if role == "GERENTE_GENERAL":
        return (
            "🤖 Comandos disponibles (gerente general)\n\n"
            "📝 Reportar\n"
            "Mandame texto, audio o foto y yo lo proceso.\n\n"
            "🔍 Consultar\n"
            "/abiertas — todas las incidencias abiertas\n"
            "/abiertas [depto] [prioridad] — filtrar\n"
            "/hab N — info completa de una habitación o zona\n"
            "/buscar palabra — buscar en todo el historial\n"
            "/historial INC-N — historial completo de una incidencia\n"
            "/help — esta ayuda\n"
            "/debug on|off — modo verboso\n\n"
            "📋 Reportes de turno\n"
            "/reporte — abrir reporte acumulativo\n"
            "/fin — cerrar reporte y procesar\n\n"
            "⚙️ Configurar\n"
            "/notificaciones — gestionar tus notificaciones"
        )
    if role == "ENCARGADO":
        dept_str = f" · {department}" if department else ""
        return (
            f"🤖 Comandos disponibles (encargado{dept_str})\n\n"
            "📝 Reportar\n"
            "Mandame texto, audio o foto y yo lo proceso.\n\n"
            "🔍 Consultar\n"
            "/abiertas — incidencias abiertas de tu departamento\n"
            "/abiertas [depto] [prioridad] — filtrar\n"
            "/hab N — info de una habitación o zona\n"
            "/buscar palabra — buscar en tu departamento\n"
            "/historial INC-N — historial de una incidencia\n"
            "/help — esta ayuda\n"
            "/debug on|off — modo verboso\n\n"
            "📋 Reportes de turno\n"
            "/reporte — abrir reporte acumulativo\n"
            "/fin — cerrar reporte y procesar"
        )
    return (
        "🤖 Comandos disponibles\n\n"
        "📝 Reportar\n"
        "Mandame texto, audio o foto y yo lo proceso.\n\n"
        "🔍 Consultar\n"
        "/abiertas — tus reportes abiertos\n"
        "/hab N — info de una habitación o zona\n"
        "/buscar palabra — buscar en tu historial\n"
        "/help — esta ayuda\n"
        "/debug on|off — modo verboso\n\n"
        "📋 Reportes de turno\n"
        "/reporte — abrir reporte acumulativo\n"
        "/fin — cerrar reporte y procesar"
    )


# ---------------------------------------------------------------------------
# Event timeline helpers (B.5)
# ---------------------------------------------------------------------------

_ACTION_EMOJI = {
    "created": "🟢",
    "tomar": "🙋",
    "en_proceso": "⏳",
    "cerrar": "✅",
    "notification_sent": "🔔",
    "notification_failed": "🔕",
    "action_rejected_already_done": "❌",
    "action_rejected_no_permission": "❌",
}

_ACTION_LABELS = {
    "created": "Creada",
    "tomar": "Tomada por",
    "en_proceso": "En proceso por",
    "cerrar": "Cerrada por",
    "notification_sent": "Notificación enviada",
    "notification_failed": "Notificación fallida",
    "action_rejected_already_done": "Intento rechazado (ya en estado",
    "action_rejected_no_permission": "Intento rechazado (sin permisos)",
}


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
        label = _ACTION_LABELS.get(action, action)

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
    import storage as _storage
    iid = incident.get("id", 0)
    display_id = _storage.generate_display_id("INCIDENCIA", iid)
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
        emoji = _ACTION_EMOJI.get(action, "•")
        from_s = e.get("from_state") or ""
        to_s = e.get("to_state") or ""
        success = e.get("success", 1)

        if action == "created":
            lines.append(f"{emoji} {time_label} — {descripcion[:50]}")
            lines.append(f"   Creada por {actor}")
        elif action in ("tomar", "en_proceso", "cerrar"):
            label = _ACTION_LABELS.get(action, action)
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
