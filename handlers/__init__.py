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


def get_employee(update, context):
    tid = update.effective_user.id
    return context.bot_data["employees"].get(tid)
