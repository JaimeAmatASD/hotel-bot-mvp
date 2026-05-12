from datetime import datetime, timedelta
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes
from brain import process_message
from handlers import get_employee, format_summary, format_summary_with_warning, format_debug_block, CONFIRM_KEYBOARD
from config.rules import CORRECTION_TIMEOUT_MINUTES
from storage import get_debug_mode


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


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = get_employee(update, context)
    if not employee:
        await update.message.reply_text("❌ No estás registrado. Contactá al administrador.")
        return

    debug_mode = get_debug_mode(update.effective_user.id)

    previous_context, timed_out = _pop_followup_state(context)
    if previous_context is None and not timed_out:
        previous_context, timed_out = _pop_correction_state(context)

    if timed_out:
        await update.message.reply_text(
            "⏱ Pasó mucho tiempo desde la corrección anterior, lo proceso como mensaje nuevo."
        )

    await update.message.reply_text("📸 Procesando foto...")

    # Download highest-resolution photo
    photo = update.message.photo[-1]
    tid = update.effective_user.id
    photos_dir = Path("data/photos") / str(tid)
    photos_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    photo_path = photos_dir / f"{timestamp}_{photo.file_id[:12]}.jpg"

    file = await context.bot.get_file(photo.file_id)
    await file.download_to_drive(str(photo_path))

    caption = update.message.caption or ""

    result = process_message(
        caption,
        employee,
        image_path=str(photo_path),
        previous_context=previous_context,
    )

    if result["tipo"] == "ERROR":
        await update.message.reply_text(
            f"❌ No pude procesar la foto.\n\n{result['descripcion']}\n\nIntentá de nuevo.",
            parse_mode="HTML",
        )
        return

    confianza = result.get("confianza", 1.0)

    if confianza < 0.6:
        await update.message.reply_text(
            "🤔 No entendí bien qué muestra la foto. ¿Podés contarme de qué se trata?"
        )
        return

    if confianza >= 0.8 and result.get("needs_followup"):
        followup = result["needs_followup"]
        context.user_data["pending"] = {
            "result": result,
            "original_text": caption,
            "image_path": str(photo_path),
        }
        context.user_data["awaiting_followup"] = True
        context.user_data["followup_started_at"] = datetime.now().isoformat()
        await update.message.reply_text(followup["question"])
        return

    context.user_data["pending"] = {
        "result": result,
        "original_text": caption,
        "image_path": str(photo_path),
    }

    if confianza < 0.8:
        summary = format_summary_with_warning(result)
    else:
        summary = format_summary(result)

    if debug_mode:
        summary += "\n\n" + format_debug_block(result)

    await update.message.reply_text(
        f"{summary}\n\n<i>¿Es correcto?</i>",
        parse_mode="HTML",
        reply_markup=CONFIRM_KEYBOARD,
    )
