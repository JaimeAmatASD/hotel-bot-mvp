"""Time and priority formatters."""
from datetime import datetime
from presenters.constants import PRIORIDAD_EMOJI


def format_relative_time(timestamp_iso: str) -> str:
    try:
        dt = datetime.fromisoformat(timestamp_iso)
        total_seconds = (datetime.now() - dt).total_seconds()
        minutes = int(total_seconds / 60)
        if minutes < 1:
            return "ahora mismo"
        if minutes < 60:
            return f"hace {minutes} min"
        hours = int(minutes / 60)
        if hours < 24:
            return f"hace {hours} h"
        days = int(hours / 24)
        return f"hace {days} día" if days == 1 else f"hace {days} días"
    except Exception:
        return "?"


def format_priority_emoji(prioridad: str) -> str:
    return PRIORIDAD_EMOJI.get(prioridad, "")
