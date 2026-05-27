"""Inline keyboards reused across handlers."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


CONFIRM_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("✅ Correcto", callback_data="confirm"),
        InlineKeyboardButton("✏️ Corregir", callback_data="correct"),
    ]
])
