"""Inline keyboards reused across handlers."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


CONFIRM_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("✅ Correcto", callback_data="confirm"),
        InlineKeyboardButton("✏️ Corregir", callback_data="correct"),
    ]
])

REPORT_DRAFT_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("✅ Listo, cerrar", callback_data="report_confirm_all"),
        InlineKeyboardButton("➕ Sumar algo", callback_data="report_add_item"),
    ]
])
