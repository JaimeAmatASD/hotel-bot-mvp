from telegram import Update
from telegram.ext import ContextTypes
from storage import get_debug_mode, set_debug_mode


async def handle_debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    args = context.args  # list of words after /debug

    if args and args[0].lower() == "on":
        set_debug_mode(tid, True)
        await update.message.reply_text(
            "🔍 Modo debug activado. Verás detalles técnicos en cada reporte."
        )
    elif args and args[0].lower() == "off":
        set_debug_mode(tid, False)
        await update.message.reply_text(
            "✅ Modo debug desactivado. Volvés a la vista normal."
        )
    else:
        current = get_debug_mode(tid)
        estado = "activado 🔍" if current else "desactivado ✅"
        await update.message.reply_text(
            f"Modo debug: <b>{estado}</b>\n\n"
            "Comandos:\n"
            "• /debug on — activar\n"
            "• /debug off — desactivar",
            parse_mode="HTML",
        )
