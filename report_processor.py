"""Handles accumulative shift report mode: keyword detection, closure processing, formatting."""
import unicodedata

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import storage
from brain import process_message
from config.settings import REPORT_OPEN_KEYWORDS, REPORT_CLOSE_KEYWORDS
from config import settings


def _normalize(text: str) -> str:
    """Lowercase + strip accents for robust keyword matching."""
    return unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()


def is_open_keyword(text: str) -> bool:
    normalized = _normalize(text.strip())
    return any(_normalize(kw) in normalized for kw in REPORT_OPEN_KEYWORDS)


def is_close_keyword(text: str) -> bool:
    normalized = _normalize(text.strip())
    return any(_normalize(kw) in normalized for kw in REPORT_CLOSE_KEYWORDS)


async def process_report_at_closure(report_id: int, employee: dict, employees: dict) -> dict:
    """
    Reads accumulated messages, classifies each one, returns decomposed dict.
    Does NOT save to classifications yet — that happens only after confirmation.
    """
    messages = storage.get_report_messages(report_id)
    items = []
    for msg in messages:
        content = msg.get("content") or ""
        photo_path = msg.get("photo_path")
        message_type = msg.get("message_type", "text")

        if not content and not photo_path:
            continue

        result = process_message(
            content,
            employee,
            image_path=photo_path if message_type == "photo" else None,
            previous_context=None,
        )
        items.append({
            "content": content,
            "photo_path": photo_path,
            "message_type": message_type,
            "result": result,
            "msg_id": msg.get("id"),
        })

    decomposed = {
        "incidencias": [i for i in items if i["result"].get("tipo") == "INCIDENCIA"],
        "guest_intel": [i for i in items if i["result"].get("tipo") == "GUEST_INTEL"],
        "observaciones": [i for i in items if i["result"].get("tipo") == "OBSERVACION"],
        "no_reportes": [i for i in items if i["result"].get("tipo") == "NO_REPORTE"],
        "errors": [i for i in items if i["result"].get("tipo") == "ERROR"],
        "all_items": items,
    }
    return decomposed


_REPORT_CONFIRM_KEYBOARD = lambda report_id: InlineKeyboardMarkup([[
    InlineKeyboardButton("✅ Todo bien", callback_data=f"report_confirm_all:{report_id}"),
    InlineKeyboardButton("✏️ Algo está mal", callback_data=f"report_correct:{report_id}"),
]])


def format_report_summary(report: dict, decomposed: dict, employee: dict) -> tuple[str, InlineKeyboardMarkup]:
    report_id = report["id"]
    display_id = storage.generate_display_id("REPORT", report_id)
    employee_name = employee.get("nombre", "")
    total = len(decomposed["all_items"])

    lines = [f"📋 Resumen del reporte {display_id} — {employee_name}", ""]
    lines.append(f"Detecté {total} ítem{'s' if total != 1 else ''}:")

    if decomposed["incidencias"]:
        lines.append(f"\n🔧 {len(decomposed['incidencias'])} incidencia{'s' if len(decomposed['incidencias']) != 1 else ''}:")
        for i, item in enumerate(decomposed["incidencias"], 1):
            ubicacion = item["result"].get("ubicacion", "")
            descripcion = item["result"].get("descripcion", "")[:50]
            lines.append(f"  {i}. {ubicacion} — {descripcion}")

    if decomposed["guest_intel"]:
        lines.append(f"\n👤 {len(decomposed['guest_intel'])} nota{'s' if len(decomposed['guest_intel']) != 1 else ''} de huésped:")
        for i, item in enumerate(decomposed["guest_intel"], 1):
            descripcion = item["result"].get("descripcion", "")[:50]
            lines.append(f"  {i}. {descripcion}")

    if decomposed["observaciones"]:
        lines.append(f"\n📊 {len(decomposed['observaciones'])} observación{'es' if len(decomposed['observaciones']) != 1 else ''}:")
        for i, item in enumerate(decomposed["observaciones"], 1):
            descripcion = item["result"].get("descripcion", "")[:50]
            lines.append(f"  {i}. {descripcion}")

    if decomposed["no_reportes"]:
        lines.append(f"\nℹ️ {len(decomposed['no_reportes'])} sin categoría")

    if decomposed["errors"]:
        lines.append(f"\n⚠️ {len(decomposed['errors'])} no pude procesar")

    lines.append("\n¿Confirmo y guardo todo?")
    return "\n".join(lines), _REPORT_CONFIRM_KEYBOARD(report_id)


def format_report_for_manager(report: dict, decomposed: dict, display_id: str) -> str:
    employee_name = report.get("employee_name", "")
    n_inc = len(decomposed["incidencias"])
    n_gi = len(decomposed["guest_intel"])
    n_obs = len(decomposed["observaciones"])
    total = len(decomposed["all_items"])

    lines = [
        f"📋 Nuevo reporte de turno — {display_id}",
        f"{employee_name} · {total} ítem{'s' if total != 1 else ''} registrados",
        "",
    ]
    if n_inc:
        lines.append(f"🔧 {n_inc} incidencia{'s' if n_inc != 1 else ''}")
    if n_gi:
        lines.append(f"👤 {n_gi} nota{'s' if n_gi != 1 else ''} de huéspedes")
    if n_obs:
        lines.append(f"📊 {n_obs} observación{'es' if n_obs != 1 else ''}")
    lines.append(f"\nVer detalle: /reporte {display_id}")
    return "\n".join(lines)


async def save_confirmed_report_items(
    report_id: int,
    items: list[dict],
    employee: dict,
    employees: dict,
    bot,
) -> list[int]:
    """Saves all items to classifications, fires notifications for INCIDENCIAS, notifies manager."""
    import notifier as _notifier

    saved_ids = []
    for item in items:
        result = item["result"]
        if result.get("tipo") in ("ERROR", None):
            continue
        classification_id = storage.save(employee, item["content"] or "", result)
        storage.link_classification_to_report(classification_id, report_id)
        saved_ids.append(classification_id)

        if result.get("tipo") == "INCIDENCIA":
            incident = {
                **result,
                "id": classification_id,
                "employee_name": employee.get("nombre"),
                "employee_dept": employee.get("departamento"),
                "photo_path": item.get("photo_path"),
            }
            await _notifier.notify_incident(
                bot=bot,
                incident=incident,
                employees=employees,
                reporter_employee=employee,
            )

    # Notify manager with summary (only if mode == "todo")
    display_id = storage.generate_display_id("REPORT", report_id)
    report = storage.get_report_with_items(report_id)
    decomposed = _regroup_items(items)
    manager_msg = format_report_for_manager(report, decomposed, display_id)

    redirect_mode = settings.NOTIFICATION_REDIRECT_MODE
    is_redirect = redirect_mode == "admin"

    for tid, emp in employees.items():
        if emp.get("rol") != "GERENTE_GENERAL":
            continue
        prefs = storage.get_notification_preferences(tid)
        if prefs.get("mode") != "todo":
            continue
        actual_tid = settings.ADMIN_TELEGRAM_ID if is_redirect else tid
        try:
            await bot.send_message(chat_id=actual_tid, text=manager_msg)
        except Exception:
            pass

    return saved_ids


def _regroup_items(items: list[dict]) -> dict:
    return {
        "incidencias": [i for i in items if i["result"].get("tipo") == "INCIDENCIA"],
        "guest_intel": [i for i in items if i["result"].get("tipo") == "GUEST_INTEL"],
        "observaciones": [i for i in items if i["result"].get("tipo") == "OBSERVACION"],
        "no_reportes": [i for i in items if i["result"].get("tipo") == "NO_REPORTE"],
        "errors": [i for i in items if i["result"].get("tipo") == "ERROR"],
        "all_items": items,
    }


async def close_report_with_timeout(bot, report: dict, employees: dict) -> None:
    """Called by the timeout job. Processes and closes the report automatically."""
    report_id = report["id"]
    tid = report["employee_telegram_id"]
    employee_name = report.get("employee_name", "")

    # Find employee dict
    employee = employees.get(tid) or {"nombre": employee_name, "departamento": report.get("employee_department"), "telegram_id": tid}

    try:
        decomposed = await process_report_at_closure(report_id, employee, employees)
        if decomposed["all_items"]:
            await save_confirmed_report_items(report_id, decomposed["all_items"], employee, employees, bot)
    except Exception:
        pass

    storage.close_report(report_id, closure_type="timeout")

    redirect_mode = settings.NOTIFICATION_REDIRECT_MODE
    actual_tid = settings.ADMIN_TELEGRAM_ID if redirect_mode == "admin" else tid
    try:
        await bot.send_message(
            chat_id=actual_tid,
            text=f"⏰ Pasaron {settings.REPORT_TIMEOUT_HOURS}h, cerré tu reporte automáticamente. "
                 f"Está procesado y guardado. Si querés agregar algo, mandá /reporte para abrir uno nuevo.",
        )
    except Exception:
        pass
