import os
import tempfile
from telegram import Update
from telegram.ext import ContextTypes
from brain import process_message
from handlers import get_employee, format_summary, CONFIRM_KEYBOARD


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = get_employee(update, context)
    if not employee:
        await update.message.reply_text("❌ No estás registrado. Contactá al administrador.")
        return

    audio = update.message.voice or update.message.audio
    if not audio:
        return

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
        )
    finally:
        os.unlink(tmp_path)

    if result["tipo"] == "ERROR":
        await update.message.reply_text(
            f"❌ No pude procesar el audio.\n\n{result['descripcion']}\n\nIntentá de nuevo.",
            parse_mode="HTML",
        )
        return

    transcription = result["_meta"].get("transcription") or ""
    context.user_data["pending"] = {"result": result, "original_text": transcription}

    parts = []
    if transcription:
        parts.append(f'🎤 <i>"{transcription}"</i>\n')
    parts.append(format_summary(result))
    parts.append("\n<i>¿Es correcto?</i>")

    await update.message.reply_text(
        "\n".join(parts),
        parse_mode="HTML",
        reply_markup=CONFIRM_KEYBOARD,
    )
