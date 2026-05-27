"""Conversation state helpers shared by all message handlers."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from config.rules import CORRECTION_TIMEOUT_MINUTES


@dataclass
class PoppedState:
    previous: dict | None
    timed_out: bool


def _pop_state(context, flag_key: str, started_key: str) -> PoppedState:
    if not context.user_data.get(flag_key):
        return PoppedState(None, False)
    started_at = context.user_data.get(started_key)
    previous = context.user_data.pop("pending", None)
    context.user_data.pop(flag_key, None)
    context.user_data.pop(started_key, None)
    if started_at:
        elapsed = datetime.now() - datetime.fromisoformat(started_at)
        if elapsed > timedelta(minutes=CORRECTION_TIMEOUT_MINUTES):
            return PoppedState(None, True)
    return PoppedState(previous, False)


def pop_followup(context) -> PoppedState:
    return _pop_state(context, "awaiting_followup", "followup_started_at")


def pop_correction(context) -> PoppedState:
    return _pop_state(context, "awaiting_correction", "correction_started_at")


def pop_previous(context) -> PoppedState:
    """Followup first (more specific), then correction."""
    f = pop_followup(context)
    if f.previous or f.timed_out:
        return f
    return pop_correction(context)
