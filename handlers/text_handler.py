from telegram import Update
from telegram.ext import ContextTypes
from brain import process_message
from handlers import get_employee, format_summary, CONFIRM_KEYBOARD


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = get_employee(update, context)
    if not employee:
        await update.message.reply_text("❌ No estás registrado. Contactá al administrador.")
        return

    text = update.message.text
    result = process_message(text, employee)

    if result["tipo"] == "ERROR":
        await update.message.reply_text(
            f"❌ No pude procesar tu mensaje.\n\n{result['descripcion']}\n\nIntentá de nuevo.",
            parse_mode="HTML",
        )
        return

    context.user_data["pending"] = {"result": result, "original_text": text}

    await update.message.reply_text(
        f"{format_summary(result)}\n\n<i>¿Es correcto?</i>",
        parse_mode="HTML",
        reply_markup=CONFIRM_KEYBOARD,
    )
