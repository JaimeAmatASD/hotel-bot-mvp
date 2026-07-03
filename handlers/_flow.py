"""Post-classification flow shared by text/audio/photo handlers."""
import html
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from presenters import (
    format_summary, format_summary_with_warning,
    format_debug_block, CONFIRM_KEYBOARD,
)
from storage import get_debug_mode
from config.enums import ReportType


async def present_result(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    result: dict,
    *,
    original_text: str,
    image_path: str | None = None,
    transcription: str | None = None,
) -> None:
    """Present the classification result to the user with confirm/correct buttons.

    Handles ERROR, low/medium/high confidence and followup question dispatch
    uniformly across text, audio, and photo handlers.
    """
    if result["tipo"] == ReportType.ERROR:
        suffix = "Intentá de nuevo."
        await update.message.reply_text(
            f"❌ No pude procesar tu mensaje.\n\n{result['descripcion']}\n\n{suffix}",
            parse_mode="HTML",
        )
        return

    confianza = result.get("confianza", 1.0)
    if confianza < 0.6:
        msg = ("🤔 No entendí bien qué muestra la foto. ¿Podés contarme de qué se trata?"
               if image_path else
               "🤔 No entendí bien tu mensaje. ¿Podés contarme de nuevo qué pasó?")
        await update.message.reply_text(msg)
        return

    pending = {"result": result, "original_text": original_text}
    if image_path:
        pending["image_path"] = image_path

    if confianza >= 0.8 and result.get("needs_followup"):
        context.user_data["pending"] = pending
        context.user_data["awaiting_followup"] = True
        context.user_data["followup_started_at"] = datetime.now().isoformat()
        if transcription:
            await update.message.reply_text(f'🎤 <i>"{html.escape(transcription)}"</i>', parse_mode="HTML")
        await update.message.reply_text(result["needs_followup"]["question"])
        return

    context.user_data["pending"] = pending
    summary = format_summary_with_warning(result) if confianza < 0.8 else format_summary(result)
    if get_debug_mode(update.effective_user.id):
        summary += "\n\n" + format_debug_block(result)

    parts = []
    if transcription:
        parts.append(f'🎤 <i>"{html.escape(transcription)}"</i>\n')
    parts.append(summary)
    parts.append("\n<i>¿Es correcto?</i>")

    await update.message.reply_text(
        "\n".join(parts), parse_mode="HTML", reply_markup=CONFIRM_KEYBOARD,
    )
