"""Item-level correction flows for the /reporte review screen.
Shared by text and audio handlers — the difference is only how the text was obtained."""
import asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from brain import process_message
from config.rules import CORRECTION_TIMEOUT_MINUTES
from config.enums import ReportType
import storage
import report_processor


async def handle_item_correction(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    employee: dict,
    text: str,
) -> bool:
    """If awaiting_item_correction is set, processes the correction and returns True.
    Otherwise returns False so the handler continues normally."""
    state = context.user_data.get("awaiting_item_correction")
    if not state:
        return False

    started_at = state.get("started_at")
    if started_at:
        elapsed = datetime.now() - datetime.fromisoformat(started_at)
        if elapsed > timedelta(minutes=CORRECTION_TIMEOUT_MINUTES):
            context.user_data.pop("awaiting_item_correction", None)
            await update.message.reply_text("⏱ Tiempo agotado. Usá /reporte para ver el resumen de nuevo.")
            return True

    item_id = state["item_id"]
    item_num = state["item_num"]
    report_items = state["report_items"]
    hours = state.get("hours", 12)

    item = next((i for i in report_items if i["id"] == item_id), None)
    previous_ctx = {"result": item, "original_text": item.get("message", "")} if item else None
    new_result = await asyncio.to_thread(process_message, text, employee, previous_context=previous_ctx)
    storage.update_classification(item_id, new_result)
    if item:
        immutable = ("id", "timestamp", "employee_name", "employee_dept", "estado", "report_id")
        item.update({k: v for k, v in new_result.items() if k not in immutable})

    context.user_data.pop("awaiting_item_correction", None)
    context.user_data["pending_report_items"] = {"items": report_items, "hours": hours}

    await update.message.reply_text(f"✅ Ítem {item_num} actualizado.")
    summary_text, keyboard = report_processor.format_report_summary(report_items, employee, hours)
    await update.message.reply_text(summary_text, reply_markup=keyboard)
    return True


async def handle_item_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    employee: dict,
    text: str,
) -> bool:
    """If awaiting_correction_item is set, processes the item number and returns True."""
    state = context.user_data.get("awaiting_correction_item")
    if not state:
        return False

    started_at = state.get("started_at")
    if started_at:
        elapsed = datetime.now() - datetime.fromisoformat(started_at)
        if elapsed > timedelta(minutes=CORRECTION_TIMEOUT_MINUTES):
            context.user_data.pop("awaiting_correction_item", None)
            await update.message.reply_text("⏱ Tiempo agotado. Usá /reporte para ver el resumen de nuevo.")
            return True

    report_items = state["report_items"]
    hours = state.get("hours", 12)
    n = len(report_items)

    try:
        num = int(text.strip())
    except (ValueError, AttributeError):
        await update.message.reply_text(f"Mandame un número entre 1 y {n}.")
        return True

    if num < 1 or num > n:
        await update.message.reply_text(f"No encontré ese ítem. Probá entre 1 y {n}.")
        return True

    item = report_items[num - 1]
    context.user_data.pop("awaiting_correction_item", None)

    if item.get("tipo") == ReportType.INCIDENCIA:
        context.user_data["pending_report_items"] = {"items": report_items, "hours": hours}
        await update.message.reply_text(
            "🔒 Las incidencias ya están en gestión y no se pueden modificar desde acá. Hablá con tu encargado."
        )
        summary_text, keyboard = report_processor.format_report_summary(report_items, employee, hours)
        await update.message.reply_text(summary_text, reply_markup=keyboard)
        return True

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
    return True
