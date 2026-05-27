"""Emoji constants for presentation."""
from config.enums import Priority, ReportType

PRIORIDAD_EMOJI = {
    Priority.CRITICA: "🔴",
    Priority.ALTA: "🟠",
    Priority.MEDIA: "🟡",
    Priority.BAJA: "🟢",
}

TIPO_EMOJI = {
    ReportType.INCIDENCIA: "🔧",
    ReportType.OBSERVACION: "👁",
    ReportType.GUEST_INTEL: "💡",
    ReportType.NO_REPORTE: "ℹ️",
    ReportType.ERROR: "❌",
}

ACTION_EMOJI = {
    "created": "🟢",
    "tomar": "🙋",
    "en_proceso": "⏳",
    "cerrar": "✅",
    "notification_sent": "🔔",
    "notification_failed": "🔕",
    "action_rejected_already_done": "❌",
    "action_rejected_no_permission": "❌",
}

ACTION_LABELS = {
    "created": "Creada",
    "tomar": "Tomada por",
    "en_proceso": "En proceso por",
    "cerrar": "Cerrada por",
    "notification_sent": "Notificación enviada",
    "notification_failed": "Notificación fallida",
    "action_rejected_already_done": "Intento rechazado (ya en estado",
    "action_rejected_no_permission": "Intento rechazado (sin permisos)",
}
