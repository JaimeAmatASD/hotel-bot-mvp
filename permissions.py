from config.rules import CATEGORY_TO_DEPARTMENT
from config.enums import Role


def get_user(telegram_id: int, employees: dict) -> dict | None:
    """Devuelve el dict del empleado o None si no está registrado."""
    return employees.get(telegram_id)


def get_role(telegram_id: int, employees: dict) -> Role | None:
    """Devuelve el rol del usuario o None si no está registrado.
    Empleados sin campo 'rol' en el JSON asumen EMPLEADO (backward compat)."""
    user = employees.get(telegram_id)
    if user is None:
        return None
    return user.get("rol", Role.EMPLEADO)


def get_department(telegram_id: int, employees: dict) -> str | None:
    """Devuelve el departamento del usuario o None si no está registrado."""
    user = employees.get(telegram_id)
    if user is None:
        return None
    return user.get("departamento")


def is_manager(telegram_id: int, employees: dict) -> bool:
    """True si es ENCARGADO o GERENTE_GENERAL."""
    return get_role(telegram_id, employees) in (Role.ENCARGADO, Role.GERENTE_GENERAL)


def _incident_department(incident: dict) -> str:
    """Traduce la categoría de una incidencia a su departamento responsable."""
    return CATEGORY_TO_DEPARTMENT.get(incident.get("categoria", ""), "GENERAL")


def can_act_on_incident(user: dict, incident: dict) -> bool:
    """
    GERENTE_GENERAL puede actuar sobre cualquier incidencia.
    ENCARGADO puede actuar sobre incidencias de su departamento.
    EMPLEADO no puede actuar (solo reportar).
    """
    rol = user.get("rol", Role.EMPLEADO)
    if rol == Role.GERENTE_GENERAL:
        return True
    if rol == Role.ENCARGADO:
        return user.get("departamento") == _incident_department(incident)
    return False


def can_see_incident(user: dict, incident: dict) -> bool:
    """
    GERENTE_GENERAL ve todas.
    ENCARGADO ve las de su departamento.
    EMPLEADO ve las que él reportó (por employee_name).
    """
    rol = user.get("rol", Role.EMPLEADO)
    if rol == Role.GERENTE_GENERAL:
        return True
    if rol == Role.ENCARGADO:
        return user.get("departamento") == _incident_department(incident)
    return incident.get("employee_name") == user.get("nombre")


def get_notification_recipients(incident: dict, employees: dict) -> list[int]:
    """
    Devuelve lista de telegram_ids que deben recibir notificación por esta incidencia.
    Incluye el encargado del departamento correspondiente (si existe) y el gerente general.
    """
    target_dept = _incident_department(incident)
    recipients: list[int] = []

    for tid, emp in employees.items():
        rol = emp.get("rol", Role.EMPLEADO)
        if rol == Role.GERENTE_GENERAL:
            recipients.append(tid)
        elif rol == Role.ENCARGADO and emp.get("departamento") == target_dept:
            recipients.append(tid)

    return recipients


def filter_visible_incidents(user: dict, incidents: list[dict]) -> list[dict]:
    """Filtra una lista de incidencias según lo que el usuario puede ver."""
    return [inc for inc in incidents if can_see_incident(user, inc)]


def can_query_department(user: dict, departamento: str) -> bool:
    """True si el usuario puede filtrar incidencias por ese departamento."""
    rol = user.get("rol", Role.EMPLEADO)
    if rol == Role.GERENTE_GENERAL:
        return True
    if rol == Role.ENCARGADO:
        return user.get("departamento", "").upper() == departamento.upper()
    return False
