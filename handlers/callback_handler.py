from telegram import Update
from telegram.ext import ContextTypes
from handlers import get_employee
from storage import save


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
        save(employee, pending["original_text"], pending["result"])
        context.user_data.pop("pending", None)

        nombre = employee["nombre"].split()[0] if employee else "empleado"
        await query.edit_message_text(f"✅ Guardado. Gracias, {nombre}.")

    elif action == "correct":
        context.user_data.pop("pending", None)
        await query.edit_message_text(
            "✏️ Describí de nuevo el problema con más detalle y lo proceso de nuevo."
        )
