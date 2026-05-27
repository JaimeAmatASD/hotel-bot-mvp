import os
import tempfile
from telegram import Update
from telegram.ext import ContextTypes
from brain import process_message
from handlers import get_employee
from handlers._state import pop_previous
from handlers._flow import present_result
from handlers._corrections import handle_item_correction, handle_item_selection
from transcriber import transcribe


async def _transcribe_audio(bot, audio, employee) -> str:
    file = await bot.get_file(audio.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        await file.download_to_drive(tmp_path)
        result = transcribe(tmp_path, language=employee.get("idioma"))
        return result.get("text", "")
    finally:
        os.unlink(tmp_path)


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = get_employee(update, context)
    if not employee:
        await update.message.reply_text("❌ No estás registrado. Contactá al administrador.")
        return

    audio = update.message.voice or update.message.audio
    if not audio:
        return

    # Item-level correction flows: transcribe first then dispatch to the shared handler.
    if context.user_data.get("awaiting_item_correction") or context.user_data.get("awaiting_correction_item"):
        await update.message.reply_text("🎧 Transcribiendo...")
        text = await _transcribe_audio(context.bot, audio, employee)
        if not text:
            await update.message.reply_text("No pude transcribir el audio. Intentá con texto.")
            return
        if await handle_item_correction(update, context, employee, text):
            return
        if await handle_item_selection(update, context, employee, text):
            return

    state = pop_previous(context)
    if state.timed_out:
        await update.message.reply_text(
            "⏱ Pasó mucho tiempo desde la corrección anterior, lo proceso como mensaje nuevo."
        )

    await update.message.reply_text("🎧 Procesando audio...")

    file = await context.bot.get_file(audio.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        await file.download_to_drive(tmp_path)
        result = process_message(
            tmp_path,
            employee,
            is_audio=True,
            language_hint=employee.get("idioma"),
            previous_context=state.previous,
        )
    finally:
        os.unlink(tmp_path)

    transcription = result.get("_meta", {}).get("transcription") or ""
    await present_result(
        update, context, result,
        original_text=transcription, transcription=transcription,
    )
