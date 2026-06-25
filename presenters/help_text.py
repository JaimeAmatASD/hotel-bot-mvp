"""Role-aware help text."""
from config.enums import Role


def get_help_text(role: str, department: str | None = None) -> str:
    if role == Role.GERENTE_GENERAL:
        return (
            "🤖 Comandos disponibles (gerente general)\n\n"
            "📝 Reportar\n"
            "Mandame texto, audio o foto y yo lo proceso.\n\n"
            "🔍 Consultar\n"
            "/mistareas — tus tareas asignadas con sus botones\n"
            "/porvalidar — incidencias resueltas esperando tu validación\n"
            "/abiertas — todas las incidencias abiertas\n"
            "/abiertas [depto] [prioridad] — filtrar\n"
            "/hab N — info completa de una habitación o zona\n"
            "/buscar palabra — buscar en todo el historial\n"
            "/historial INC-N — historial completo de una incidencia\n"
            "/help — esta ayuda\n"
            "/debug on|off — modo verboso\n\n"
            "📋 Informe de turno (todo lo del turno se guarda solo)\n"
            "/reporte — armá tu informe del turno (lo cargado)\n"
            "/fin — cerrá y enviá el informe (igual que /reporte)\n\n"
            "⚙️ Configurar\n"
            "/notificaciones — gestionar tus notificaciones"
        )
    if role == Role.ENCARGADO:
        dept_str = f" · {department}" if department else ""
        return (
            f"🤖 Comandos disponibles (encargado{dept_str})\n\n"
            "📝 Reportar\n"
            "Mandame texto, audio o foto y yo lo proceso.\n\n"
            "🔍 Consultar\n"
            "/mistareas — tus tareas asignadas con sus botones\n"
            "/porvalidar — incidencias resueltas esperando tu validación\n"
            "/abiertas — incidencias abiertas de tu departamento\n"
            "/abiertas [depto] [prioridad] — filtrar\n"
            "/hab N — info de una habitación o zona\n"
            "/buscar palabra — buscar en tu departamento\n"
            "/historial INC-N — historial de una incidencia\n"
            "/help — esta ayuda\n"
            "/debug on|off — modo verboso\n\n"
            "📋 Informe de turno (todo lo del turno se guarda solo)\n"
            "/reporte — armá tu informe del turno (lo cargado)\n"
            "/fin — cerrá y enviá el informe (igual que /reporte)"
        )
    return (
        "🤖 Comandos disponibles\n\n"
        "📝 Reportar\n"
        "Mandame texto, audio o foto y yo lo proceso.\n\n"
        "🔍 Consultar\n"
        "/mistareas — tus tareas asignadas con sus botones\n"
        "/abiertas — tus reportes abiertos\n"
        "/hab N — info de una habitación o zona\n"
        "/buscar palabra — buscar en tu historial\n"
        "/help — esta ayuda\n"
        "/debug on|off — modo verboso\n\n"
        "📋 Reportes de turno\n"
        "/reporte — abrir reporte acumulativo\n"
        "/fin — cerrá y enviá el informe (igual que /reporte)"
    )
