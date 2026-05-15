from telegram import Update
from telegram.ext import ContextTypes
from storage import (
    get_debug_mode, set_debug_mode,
    get_notification_preferences, set_notification_mode, toggle_excluded_department,
)
from permissions import get_role


async def handle_debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    args = context.args  # list of words after /debug

    if args and args[0].lower() == "on":
        set_debug_mode(tid, True)
        await update.message.reply_text(
            "🔍 Modo debug activado. Verás detalles técnicos en cada reporte."
        )
    elif args and args[0].lower() == "off":
        set_debug_mode(tid, False)
        await update.message.reply_text(
            "✅ Modo debug desactivado. Volvés a la vista normal."
        )
    else:
        current = get_debug_mode(tid)
        estado = "activado 🔍" if current else "desactivado ✅"
        await update.message.reply_text(
            f"Modo debug: <b>{estado}</b>\n\n"
            "Comandos:\n"
            "• /debug on — activar\n"
            "• /debug off — desactivar",
            parse_mode="HTML",
        )


async def handle_notificaciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    employees = context.bot_data.get("employees", {})
    role = get_role(tid, employees)

    if role != "GERENTE_GENERAL":
        await update.message.reply_text("Este comando es solo para el gerente general.")
        return

    args = context.args or []

    if not args:
        prefs = get_notification_preferences(tid)
        mode = prefs["mode"]
        excluded = prefs["excluded_departments"]
        excluded_str = ", ".join(excluded) if excluded else "ninguno"
        await update.message.reply_text(
            f"🔔 <b>Configuración de notificaciones</b>\n\n"
            f"Modo actual: <b>{mode}</b>\n"
            f"Departamentos excluidos: {excluded_str}\n\n"
            f"Opciones:\n"
            f"• /notificaciones todo — todas las incidencias\n"
            f"• /notificaciones criticas — solo CRITICA y ALTA (default)\n"
            f"• /notificaciones solo_criticas — solo CRITICA\n"
            f"• /notificaciones nada — sin notificaciones en tiempo real\n"
            f"• /notificaciones depto NOMBRE — excluir/incluir un departamento",
            parse_mode="HTML",
        )
        return

    cmd = args[0].lower()
    valid_modes = {"todo", "criticas", "solo_criticas", "nada"}

    if cmd in valid_modes:
        set_notification_mode(tid, cmd)
        await update.message.reply_text(f"✅ Modo de notificaciones: <b>{cmd}</b>", parse_mode="HTML")
        return

    if cmd == "depto" and len(args) >= 2:
        dept = args[1].upper()
        is_excluded = toggle_excluded_department(tid, dept)
        estado = "excluido ❌" if is_excluded else "incluido ✅"
        await update.message.reply_text(f"Departamento <b>{dept}</b>: {estado}", parse_mode="HTML")
        return

    await update.message.reply_text(
        "Opción no reconocida. Usá /notificaciones para ver las opciones."
    )
