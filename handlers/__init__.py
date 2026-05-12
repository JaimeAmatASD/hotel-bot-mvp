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
