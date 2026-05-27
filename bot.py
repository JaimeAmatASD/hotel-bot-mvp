import json
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from telegram.ext import Application, MessageHandler, CallbackQueryHandler, CommandHandler, filters

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

from handlers.text_handler import handle_text
from handlers.audio_handler import handle_audio
from handlers.photo_handler import handle_photo
from handlers.callback_handler import handle_callback
from handlers.command_handler import (
    handle_debug, handle_notificaciones,
    handle_abiertas, handle_hab, handle_buscar, handle_help, handle_historial,
    handle_reporte, handle_fin,
)


def load_employees() -> dict:
    path = Path(__file__).parent / "config" / "employees.json"
    data = json.loads(path.read_text())
    return {e["telegram_id"]: e for e in data["employees"]}


def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    employees = load_employees()

    app = Application.builder().token(token).build()
    app.bot_data["employees"] = employees

    app.add_handler(CommandHandler("debug", handle_debug))
    app.add_handler(CommandHandler("notificaciones", handle_notificaciones))
    app.add_handler(CommandHandler("abiertas", handle_abiertas))
    app.add_handler(CommandHandler("hab", handle_hab))
    app.add_handler(CommandHandler("buscar", handle_buscar))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("historial", handle_historial))
    app.add_handler(CommandHandler("reporte", handle_reporte))
    app.add_handler(CommandHandler("fin", handle_fin))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
    app.add_handler(CallbackQueryHandler(handle_callback))

    async def unknown_command(update, context):
        await update.message.reply_text(
            "❓ Ese comando no existe. Mandá /help para ver los disponibles."
        )
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    import storage
    from storage.migrations import apply_pending
    storage.init_db()
    apply_pending()  # no-op por ahora pero deja el hook listo

    import sheets_sync
    sheets_sync.ensure_headers()

    print("Bot iniciado. Ctrl+C para detener.")
    app.run_polling()


if __name__ == "__main__":
    main()
