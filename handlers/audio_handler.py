import os
import tempfile
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from brain import process_message
from handlers import get_employee, format_summary, format_summary_with_warning, CONFIRM_KEYBOARD
from config.rules import CORRECTION_TIMEOUT_MINUTES


def _pop_followup_state(context) -> tuple[dict | None, bool]:
    """Returns (previous_pending, timed_out). Clears followup state regardless."""
    if not context.user_data.get("awaiting_followup"):
        return None, False

    started_at = context.user_data.get("followup_started_at")
    previous = context.user_data.pop("pending", None)
    context.user_data.pop("awaiting_followup", None)
    context.user_data.pop("followup_started_at", None)

    if started_at:
        elapsed = datetime.now() - datetime.fromisoformat(started_at)
        if elapsed > timedelta(minutes=CORRECTION_TIMEOUT_MINUTES):
            return None, True

    return previous, False


def _pop_correction_state(context) -> tuple[dict | None, bool]:
    """Returns (previous_pending, timed_out). Clears correction state regardless."""
    if not context.user_data.get("awaiting_correction"):
        return None, False

    started_at = context.user_data.get("correction_started_at")
    previous = context.user_data.pop("pending", None)
    context.user_data.pop("awaiting_correction", None)
    context.user_data.pop("correction_started_at", None)

    if started_at:
        elapsed = datetime.now() - datetime.fromisoformat(started_at)
        if elapsed > timedelta(minutes=CORRECTION_TIMEOUT_MINUTES):
            return None, True

    return previous, False


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = get_employee(update, context)
    if not employee:
        await update.message.reply_text("❌ No estás registrado. Contactá al administrador.")
        return

    # Followup (bot-initiated) has priority over correction (user-initiated)
    previous_context, timed_out = _pop_followup_state(context)
    if previous_context is None and not timed_out:
        previous_context, timed_out = _pop_correction_state(context)

    if timed_out:
        await update.message.reply_text(
            "⏱ Pasó mucho tiempo desde la corrección anterior, lo proceso como mensaje nuevo."
        )

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
            previous_context=previous_context,
        )
    finally:
        os.unlink(tmp_path)

    if result["tipo"] == "ERROR":
        await update.message.reply_text(
            f"❌ No pude procesar el audio.\n\n{result['descripcion']}\n\nIntentá de nuevo.",
            parse_mode="HTML",
        )
        return

    confianza = result.get("confianza", 1.0)

    if confianza < 0.6:
        await update.message.reply_text(
            "🤔 No entendí bien tu mensaje. ¿Podés contarme de nuevo qué pasó?"
        )
        return

    transcription = result["_meta"].get("transcription") or ""

    if confianza >= 0.8 and result.get("needs_followup"):
        followup = result["needs_followup"]
        context.user_data["pending"] = {"result": result, "original_text": transcription}
        context.user_data["awaiting_followup"] = True
        context.user_data["followup_started_at"] = datetime.now().isoformat()
        if transcription:
            await update.message.reply_text(f'🎤 <i>"{transcription}"</i>', parse_mode="HTML")
        await update.message.reply_text(followup["question"])
        return

    context.user_data["pending"] = {"result": result, "original_text": transcription}

    if confianza < 0.8:
        summary = format_summary_with_warning(result)
    else:
        summary = format_summary(result)

    parts = []
    if transcription:
        parts.append(f'🎤 <i>"{transcription}"</i>\n')
    parts.append(summary)
    parts.append("\n<i>¿Es correcto?</i>")

    await update.message.reply_text(
        "\n".join(parts),
        parse_mode="HTML",
        reply_markup=CONFIRM_KEYBOARD,
    )
