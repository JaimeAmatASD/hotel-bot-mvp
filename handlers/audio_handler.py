import os
import tempfile
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from brain import process_message
from handlers import get_employee, format_summary, format_summary_with_warning, format_debug_block, CONFIRM_KEYBOARD
from handlers._state import pop_previous
from config.rules import CORRECTION_TIMEOUT_MINUTES
from storage import get_debug_mode
from transcriber import transcribe
import storage
import report_processor


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

    # Awaiting correction text for a specific item (OBS/GUEST_INTEL)
    if context.user_data.get("awaiting_item_correction"):
        state = context.user_data["awaiting_item_correction"]
        started_at = state.get("started_at")
        if started_at:
            elapsed = datetime.now() - datetime.fromisoformat(started_at)
            if elapsed > timedelta(minutes=CORRECTION_TIMEOUT_MINUTES):
                context.user_data.pop("awaiting_item_correction", None)
                await update.message.reply_text("⏱ Tiempo agotado. Usá /reporte para ver el resumen de nuevo.")
                return

        await update.message.reply_text("🎧 Transcribiendo corrección...")
        text = await _transcribe_audio(context.bot, audio, employee)
        if not text:
            await update.message.reply_text("No pude transcribir el audio. Intentá con texto.")
            return

        item_id = state["item_id"]
        item_num = state["item_num"]
        report_items = state["report_items"]
        hours = state.get("hours", 12)

        item = next((i for i in report_items if i["id"] == item_id), None)
        previous_ctx = {"result": item, "original_text": item.get("message", "")} if item else None
        new_result = process_message(text, employee, previous_context=previous_ctx)

        storage.update_classification(item_id, new_result)
        if item:
            item.update({k: v for k, v in new_result.items() if k not in ("id", "timestamp", "employee_name", "employee_dept", "estado", "report_id")})

        context.user_data.pop("awaiting_item_correction", None)
        context.user_data["pending_report_items"] = {"items": report_items, "hours": hours}

        await update.message.reply_text(f"✅ Ítem {item_num} actualizado.")
        summary_text, keyboard = report_processor.format_report_summary(report_items, employee, hours)
        await update.message.reply_text(summary_text, reply_markup=keyboard)
        return

    # Awaiting item number for correction selection
    if context.user_data.get("awaiting_correction_item"):
        state = context.user_data["awaiting_correction_item"]
        started_at = state.get("started_at")
        if started_at:
            elapsed = datetime.now() - datetime.fromisoformat(started_at)
            if elapsed > timedelta(minutes=CORRECTION_TIMEOUT_MINUTES):
                context.user_data.pop("awaiting_correction_item", None)
                await update.message.reply_text("⏱ Tiempo agotado. Usá /reporte para ver el resumen de nuevo.")
                return

        await update.message.reply_text("🎧 Transcribiendo número de ítem...")
        text = await _transcribe_audio(context.bot, audio, employee)

        report_items = state["report_items"]
        hours = state.get("hours", 12)
        n = len(report_items)
        try:
            num = int(text.strip())
        except (ValueError, AttributeError):
            await update.message.reply_text(f"Mandame un número entre 1 y {n}.")
            return

        if num < 1 or num > n:
            await update.message.reply_text(f"No encontré ese ítem. Probá entre 1 y {n}.")
            return

        item = report_items[num - 1]
        context.user_data.pop("awaiting_correction_item", None)

        if item.get("tipo") == "INCIDENCIA":
            context.user_data["pending_report_items"] = {"items": report_items, "hours": hours}
            await update.message.reply_text(
                "🔒 Las incidencias ya están en gestión y no se pueden modificar desde acá. Hablá con tu encargado."
            )
            summary_text, keyboard = report_processor.format_report_summary(report_items, employee, hours)
            await update.message.reply_text(summary_text, reply_markup=keyboard)
            return

        context.user_data["awaiting_item_correction"] = {
            "item_id": item["id"],
            "item_num": num,
            "report_items": report_items,
            "hours": hours,
            "started_at": datetime.now().isoformat(),
        }
        await update.message.reply_text(
            f"Decime qué corregir o agregar (texto o audio). Estoy reprocesando el ítem {num}: "
            f"{(item.get('descripcion') or '')[:60]}"
        )
        return

    # Normal flow
    tid = update.effective_user.id
    debug_mode = get_debug_mode(tid)

    state = pop_previous(context)
    previous_context, timed_out = state.previous, state.timed_out

    if timed_out:
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

    if debug_mode:
        summary += "\n\n" + format_debug_block(result)

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
