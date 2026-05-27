"""Notifier package — formatting, sending, filtering, and state-change notifications.

Public API: notify_incident, notify_employee_state_change, format_notification_message,
build_keyboard_for_state, send_notification_with_logging.

`storage` and `settings` are re-exported so existing tests can patch
`notifier.storage.<fn>` and `notifier.settings.<attr>` without changes.
"""
import storage
from config import settings

from notifier.format import (
    format_notification_message,
    build_keyboard_for_state,
)
from notifier.send import send_notification_with_logging
from notifier.dispatch import notify_incident
from notifier.state_change import notify_employee_state_change
from notifier.sender import MessageSender, TelegramMessageSender, as_sender
