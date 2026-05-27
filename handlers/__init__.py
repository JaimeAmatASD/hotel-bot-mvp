"""Handlers package — routing layer. Presentation lives in `presenters/`."""

def get_employee(update, context):
    tid = update.effective_user.id
    return context.bot_data["employees"].get(tid)


# Re-exports for backwards compat with existing callers; new code should import from `presenters`.
from presenters import (
    PRIORIDAD_EMOJI, TIPO_EMOJI, CONFIRM_KEYBOARD,
    format_summary, format_summary_with_warning, format_debug_block,
    format_relative_time, format_priority_emoji,
    format_incident_line, format_incident_list, format_room_view,
    get_help_text, format_incident_history,
    build_timeline_text, calculate_total_time,
)
