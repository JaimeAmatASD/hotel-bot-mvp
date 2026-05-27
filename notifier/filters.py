"""Filter pure functions: does this gerente want this notification?"""
from config.enums import NotificationMode, Priority


def should_notify_gerente(incident: dict, prefs: dict) -> bool:
    """Applies gerente filters. CRITICA always passes regardless of mode."""
    prioridad = incident.get("prioridad", "")
    mode = prefs.get("mode", NotificationMode.CRITICAS)

    if prioridad == Priority.CRITICA:
        return True
    if mode == NotificationMode.NADA:
        return False
    if mode == NotificationMode.SOLO_CRITICAS:
        return False
    if mode == NotificationMode.CRITICAS:
        return prioridad == Priority.ALTA
    if mode == NotificationMode.TODO:
        excluded = prefs.get("excluded_departments", [])
        return incident.get("categoria") not in excluded
    return True
