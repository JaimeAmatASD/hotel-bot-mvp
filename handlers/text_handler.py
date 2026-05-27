from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from brain import process_message
from handlers import get_employee, format_summary, format_summary_with_warning, format_debug_block, CONFIRM_KEYBOARD
from handlers._state import pop_previous
from config.rules import CORRECTION_TIMEOUT_MINUTES
from storage import get_debug_mode
import storage
import report_processor


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = get_employee(update, context)
    if not employee:
        await update.message.reply_text("❌ No estás registrado. Contactá al administrador.")
        return

    text = update.message.text

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
        item_id = state["item_id"]
        item_num = state["item_num"]
        report_items = state["report_items"]
        hours = state.get("hours", 12)

        item = next((i for i in report_items if i["id"] == item_id), None)
        previous_ctx = {"result": item, "original_text": item.get("message", "")} if item else None
        new_result = process_message(text, employee, previous_context=previous_ctx)

        storage.update_classification(item_id, new_result)

        # Update item in-memory so re-shown summary reflects the change
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

        report_items = state["report_items"]
        hours = state.get("hours", 12)
        n = len(report_items)

        try:
            num = int(text.strip())
        except ValueError:
            await update.message.reply_text(f"Mandame un número entre 1 y {n}.")
            return

        if num < 1 or num > n:
            await update.message.reply_text(f"No encontré ese ítem. Probá entre 1 y {n}.")
            return

        item = report_items[num - 1]
        context.user_data.pop("awaiting_correction_item", None)

        if item.get("tipo") == "INCIDENCIA":
            # Re-show summary with buttons so they can try another item
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
