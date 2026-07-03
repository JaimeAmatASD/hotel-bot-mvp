import asyncio
from datetime import datetime
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes
from brain import process_message
from handlers import get_employee
from handlers._state import pop_previous
from handlers._flow import present_result


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

    state = pop_previous(context)
    if state.timed_out:
        await update.message.reply_text(
            "⏱ Pasó mucho tiempo desde la corrección anterior, lo proceso como mensaje nuevo."
        )

    await update.message.reply_text("📸 Procesando foto...")

    result = await asyncio.to_thread(
        process_message,
        caption,
        employee,
        image_path=str(photo_path),
        previous_context=state.previous,
    )

    await present_result(
        update, context, result,
        original_text=caption, image_path=str(photo_path),
    )
