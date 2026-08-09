import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from brain import process_message
from handlers import get_employee
from handlers._state import pop_previous
from handlers._flow import present_result


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = get_employee(update, context)
    if not employee:
        await update.message.reply_text("❌ No estás registrado. Contactá al administrador.")
        return

    text = update.message.text

    state = pop_previous(context)
    if state.timed_out:
        await update.message.reply_text(
            "⏱ Pasó mucho tiempo desde la corrección anterior, lo proceso como mensaje nuevo."
        )

    # En thread: la llamada a Gemini es síncrona y no debe bloquear el event loop
    result = await asyncio.to_thread(process_message, text, employee, previous_context=state.previous)
    await present_result(update, context, result, original_text=text)
