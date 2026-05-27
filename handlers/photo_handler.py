from datetime import datetime
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes
from brain import process_message
from handlers import get_employee, format_summary, format_summary_with_warning, format_debug_block, CONFIRM_KEYBOARD
from handlers._state import pop_previous
from storage import get_debug_mode
import storage


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = get_employee(update, context)
    if not employee:
        await update.message.reply_text("❌ No estás registrado. Contactá al administrador.")
        return

    tid = update.effective_user.id

    photo = update.message.photo[-1]
    photos_dir = Path("data/photos") / str(tid)
    photos_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    photo_path = photos_dir / f"{timestamp}_{photo.file_id[:12]}.jpg"
    file = await context.bot.get_file(photo.file_id)
    await file.download_to_drive(str(photo_path))

    caption = update.message.caption or ""

    debug_mode = get_debug_mode(tid)

    state = pop_previous(context)
    previous_context, timed_out = state.previous, state.timed_out

    if timed_out:
        await update.message.reply_text(
            "⏱ Pasó mucho tiempo desde la corrección anterior, lo proceso como mensaje nuevo."
        )

    await update.message.reply_text("📸 Procesando foto...")

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
