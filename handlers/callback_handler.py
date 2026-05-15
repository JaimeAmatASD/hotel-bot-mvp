from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from handlers import get_employee
from storage import save
import notifier


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action = query.data
    pending = context.user_data.get("pending")

    if action == "confirm":
        if not pending:
            await query.edit_message_text("❌ No hay reporte pendiente.")
            return

        employee = get_employee(update, context)
        result = pending["result"]
        incident_id = save(employee, pending["original_text"], result)
        context.user_data.pop("pending", None)

        nombre = employee["nombre"].split()[0] if employee else "empleado"
        await query.edit_message_text(f"✅ Guardado. Gracias, {nombre}.")

        if result.get("tipo") == "INCIDENCIA":
            incident = {
                **result,
                "id": incident_id,
                "employee_name": employee["nombre"],
                "employee_dept": employee.get("departamento"),
                "photo_path": result.get("_meta", {}).get("photo_path"),
            }
            await notifier.notify_incident(
                bot=context.bot,
                incident=incident,
                employees=context.bot_data["employees"],
                reporter_employee=employee,
            )

    elif action == "correct":
        context.user_data["awaiting_correction"] = True
        context.user_data["correction_started_at"] = datetime.now().isoformat()
        await query.edit_message_text(
            "✏️ Decime qué corregir o agregar (texto o audio). Recuerdo lo que reportaste antes y lo reproceso con tu corrección."
        )
