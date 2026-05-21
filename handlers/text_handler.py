from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from brain import process_message
from handlers import get_employee, format_summary, format_summary_with_warning, format_debug_block, CONFIRM_KEYBOARD
from config.rules import CORRECTION_TIMEOUT_MINUTES
from storage import get_debug_mode
import storage
import report_processor


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


async def _do_report_open(update, context, employee):
    tid = update.effective_user.id
    open_rep = storage.get_open_report_for_employee(tid)
    if open_rep:
        msg_count = len(storage.get_report_messages(open_rep["id"]))
        await update.message.reply_text(
            f"Ya tenés un reporte abierto con {msg_count} ítem{'s' if msg_count != 1 else ''}. "
            f"Mandame contenido o /fin para cerrarlo."
        )
        return
    report_id = storage.open_report(employee)
    context.user_data["open_report_id"] = report_id
    await update.message.reply_text(
        "📋 Modo reporte abierto.\n\n"
        "Mandame todo lo del turno: incidencias, notas de huéspedes, observaciones. "
        "Texto, audio o foto. Puedo recibir muchos mensajes.\n\n"
        "Cuando termines, mandá /fin o decime \"cierre de reporte\"."
    )


async def _do_report_close(update, context, open_report, employee):
    report_id = open_report["id"]
    msg_count = len(storage.get_report_messages(report_id))
    if msg_count == 0:
        storage.close_report(report_id, "manual")
        context.user_data.pop("open_report_id", None)
        await update.message.reply_text("📋 Reporte cerrado (sin ítems).")
        return
    await update.message.reply_text(f"📋 Procesando tu reporte... Voy a clasificar {msg_count} ítem{'s' if msg_count != 1 else ''}.")
    decomposed = await report_processor.process_report_at_closure(report_id, employee, context.bot_data["employees"])
    context.user_data["pending_report"] = {"report_id": report_id, "items": decomposed["all_items"]}
    context.user_data.pop("open_report_id", None)
    text, keyboard = report_processor.format_report_summary(open_report, decomposed, employee)
    await update.message.reply_text(text, reply_markup=keyboard)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = get_employee(update, context)
    if not employee:
        await update.message.reply_text("❌ No estás registrado. Contactá al administrador.")
        return

    tid = update.effective_user.id
    text = update.message.text

    # Report correction mode
    if context.user_data.get("awaiting_report_correction"):
        pending_report = context.user_data.get("pending_report")
        if pending_report and report_processor._normalize(text).startswith("rehacer"):
            context.user_data.pop("awaiting_report_correction", None)
            context.user_data.pop("pending_report", None)
            report_id = pending_report["report_id"]
            # Reopen the report (status back to OPEN)
            with storage._conn() as con:
                con.execute("UPDATE reports SET status='OPEN', closed_at=NULL WHERE id=?", (report_id,))
            context.user_data["open_report_id"] = report_id
            msg_count = len(storage.get_report_messages(report_id))
            await update.message.reply_text(
                f"📋 Reporte reabierto con {msg_count} ítems anteriores. Podés añadir más o /fin para cerrar."
            )
        else:
            context.user_data.pop("awaiting_report_correction", None)
            await update.message.reply_text("✓ Anotada la corrección. Procesando resumen actualizado...")
            report_id = pending_report["report_id"] if pending_report else None
            if report_id:
                open_rep = {"id": report_id}
                decomposed = await report_processor.process_report_at_closure(report_id, employee, context.bot_data["employees"])
                context.user_data["pending_report"] = {"report_id": report_id, "items": decomposed["all_items"]}
                summary_text, keyboard = report_processor.format_report_summary(open_rep, decomposed, employee)
                await update.message.reply_text(summary_text, reply_markup=keyboard)
        return

    # Report mode check
    open_report = storage.get_open_report_for_employee(tid)
    if open_report:
        if report_processor.is_close_keyword(text):
            await _do_report_close(update, context, open_report, employee)
            return
        storage.add_message_to_report(open_report["id"], "text", text)
        await update.message.reply_text("✓ anotado")
        return

    if report_processor.is_open_keyword(text):
        await _do_report_open(update, context, employee)
        return

    # Normal flow
    debug_mode = get_debug_mode(tid)

    previous_context, timed_out = _pop_followup_state(context)
    if previous_context is None and not timed_out:
        previous_context, timed_out = _pop_correction_state(context)

    if timed_out:
        await update.message.reply_text(
            "⏱ Pasó mucho tiempo desde la corrección anterior, lo proceso como mensaje nuevo."
        )

    result = process_message(text, employee, previous_context=previous_context)

    if result["tipo"] == "ERROR":
        await update.message.reply_text(
            f"❌ No pude procesar tu mensaje.\n\n{result['descripcion']}\n\nIntentá de nuevo.",
            parse_mode="HTML",
        )
        return

    confianza = result.get("confianza", 1.0)

    if confianza < 0.6:
        await update.message.reply_text(
            "🤔 No entendí bien tu mensaje. ¿Podés contarme de nuevo qué pasó?"
        )
        return

    if confianza >= 0.8 and result.get("needs_followup"):
        followup = result["needs_followup"]
        context.user_data["pending"] = {"result": result, "original_text": text}
        context.user_data["awaiting_followup"] = True
        context.user_data["followup_started_at"] = datetime.now().isoformat()
        await update.message.reply_text(followup["question"])
        return

    context.user_data["pending"] = {"result": result, "original_text": text}

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
