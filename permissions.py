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


def _is_reporter(user: dict, incident: dict) -> bool:
    """Identidad por telegram_id; fallback por nombre para filas anteriores a la columna."""
    reporter_tid = incident.get("employee_telegram_id")
    if reporter_tid is not None:
        try:
            return int(reporter_tid) == int(user.get("telegram_id", -1))
        except (TypeError, ValueError):
            return False
    return incident.get("employee_name") == user.get("nombre")


def can_see_incident(user: dict, incident: dict) -> bool:
    """
    GERENTE_GENERAL ve todas.
    ENCARGADO ve las de su departamento.
    EMPLEADO ve las que él reportó y las asignadas a él.
    """
    rol = user.get("rol", Role.EMPLEADO)
    if rol == Role.GERENTE_GENERAL:
        return True
    if rol == Role.ENCARGADO:
        return user.get("departamento") == _incident_department(incident)
    if _is_reporter(user, incident):
        return True
    return _is_assignee(user, incident)


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


from config.transitions import MANAGEMENT_ACTIONS, EXECUTION_ACTIONS


def _is_assignee(user: dict, incident: dict) -> bool:
    assigned = incident.get("assigned_to_telegram_id")
    if assigned is None:
        return False
    try:
        return int(assigned) == int(user.get("telegram_id", -1))
    except (TypeError, ValueError):
        return False


def can_do_action(user: dict, incident: dict, action: str) -> bool:
    """Permiso unificado por acción.

    - Acciones de gestión (asignar/tomar/reasignar/validar/reabrir/cancelar):
      solo manager con alcance sobre la incidencia (`can_act_on_incident`).
    - Acciones de ejecución (comenzar/terminado): el asignado, o un manager.
    """
    if action in EXECUTION_ACTIONS:
        return _is_assignee(user, incident) or can_act_on_incident(user, incident)
    if action in MANAGEMENT_ACTIONS:
        return can_act_on_incident(user, incident)
    return False


def assignable_targets(actor: dict, employees: dict, departamento: str) -> list[tuple[int, dict]]:
    """Empleados y encargados de `departamento` a quienes se les puede asignar una tarea."""
    out = []
    for tid, emp in employees.items():
        if emp.get("departamento") == departamento and emp.get("rol", Role.EMPLEADO) in (Role.EMPLEADO, Role.ENCARGADO):
            out.append((tid, emp))
    return out


def assignable_departments(actor: dict, employees: dict) -> list[str]:
    """Departamentos a los que el actor puede asignar (solo el gerente usa el menú cross-depto)."""
    return sorted({
        emp.get("departamento") for emp in employees.values()
        if emp.get("departamento") and emp.get("rol", Role.EMPLEADO) in (Role.EMPLEADO, Role.ENCARGADO)
    })
