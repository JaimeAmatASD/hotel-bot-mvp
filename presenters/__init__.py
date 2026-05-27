"""Presentation layer: formatters, keyboards, emojis. No I/O."""
from presenters.constants import PRIORIDAD_EMOJI, TIPO_EMOJI
from presenters.keyboards import CONFIRM_KEYBOARD
from presenters.format_summary import (
    format_summary, format_summary_with_warning, format_debug_block,
)
from presenters.format_relative import format_relative_time, format_priority_emoji
from presenters.format_incidents import (
    format_incident_line, format_incident_list, format_room_view,
)
from presenters.format_history import (
    build_timeline_text, calculate_total_time, format_incident_history,
)
from presenters.help_text import get_help_text
