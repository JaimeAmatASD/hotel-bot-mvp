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
