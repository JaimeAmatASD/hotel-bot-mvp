import json
from pathlib import Path

import pytest

from permissions import (
    can_act_on_incident,
    can_see_incident,
    filter_visible_incidents,
    get_department,
    get_notification_recipients,
    get_role,
    get_user,
    is_manager,
)

# ---------------------------------------------------------------------------
# Fixtures inline — no dependen de employees.json para ser portables
# ---------------------------------------------------------------------------

EMPLOYEES = {
    1001: {"telegram_id": 1001, "nombre": "Ana Empleada", "departamento": "SPA", "idioma": "es", "rol": "EMPLEADO"},
    2001: {"telegram_id": 2001, "nombre": "Carlos Enc", "departamento": "MANTENIMIENTO", "idioma": "es", "rol": "ENCARGADO"},
    2002: {"telegram_id": 2002, "nombre": "Laura Enc", "departamento": "HOUSEKEEPING", "idioma": "es", "rol": "ENCARGADO"},
    3001: {"telegram_id": 3001, "nombre": "Alfredo Gte", "departamento": "GENERAL", "idioma": "es", "rol": "GERENTE_GENERAL"},
    # Sin campo rol — backward compat
    9999: {"telegram_id": 9999, "nombre": "Viejo Empleado", "departamento": "SPA", "idioma": "es"},
}

INC_MANTENIMIENTO = {"categoria": "MANTENIMIENTO", "employee_name": "Ana Empleada"}
INC_LIMPIEZA = {"categoria": "LIMPIEZA", "employee_name": "Ana Empleada"}
INC_OTRA_PERSONA = {"categoria": "MANTENIMIENTO", "employee_name": "Otro Empleado"}
INC_SIN_CATEGORIA = {"categoria": "DESCONOCIDA", "employee_name": "Ana Empleada"}


# ---------------------------------------------------------------------------
# get_role
# ---------------------------------------------------------------------------

def test_get_role_empleado():
    assert get_role(1001, EMPLOYEES) == "EMPLEADO"


def test_get_role_encargado():
    assert get_role(2001, EMPLOYEES) == "ENCARGADO"


def test_get_role_gerente():
    assert get_role(3001, EMPLOYEES) == "GERENTE_GENERAL"


def test_get_role_desconocido_devuelve_none():
    assert get_role(8888, EMPLOYEES) is None


def test_get_role_sin_campo_rol_devuelve_empleado():
    """Backward compat: empleados sin campo 'rol' asumen EMPLEADO."""
    assert get_role(9999, EMPLOYEES) == "EMPLEADO"


# ---------------------------------------------------------------------------
# is_manager
# ---------------------------------------------------------------------------

def test_is_manager_empleado_es_false():
    assert is_manager(1001, EMPLOYEES) is False


def test_is_manager_encargado_es_true():
    assert is_manager(2001, EMPLOYEES) is True


def test_is_manager_gerente_es_true():
    assert is_manager(3001, EMPLOYEES) is True


def test_is_manager_desconocido_es_false():
    assert is_manager(8888, EMPLOYEES) is False


# ---------------------------------------------------------------------------
# can_act_on_incident
# ---------------------------------------------------------------------------

def test_can_act_encargado_su_departamento():
    carlos = EMPLOYEES[2001]
    assert can_act_on_incident(carlos, INC_MANTENIMIENTO) is True


def test_can_act_encargado_departamento_ajeno():
    carlos = EMPLOYEES[2001]
    assert can_act_on_incident(carlos, INC_LIMPIEZA) is False


def test_can_act_gerente_cualquier_incidencia():
    alfredo = EMPLOYEES[3001]
    assert can_act_on_incident(alfredo, INC_LIMPIEZA) is True
    assert can_act_on_incident(alfredo, INC_MANTENIMIENTO) is True


def test_can_act_empleado_es_false():
    ana = EMPLOYEES[1001]
    assert can_act_on_incident(ana, INC_MANTENIMIENTO) is False


# ---------------------------------------------------------------------------
# can_see_incident
# ---------------------------------------------------------------------------

def test_can_see_encargado_su_departamento():
    carlos = EMPLOYEES[2001]
    assert can_see_incident(carlos, INC_MANTENIMIENTO) is True


def test_can_see_encargado_no_ve_otro_dept():
    carlos = EMPLOYEES[2001]
    assert can_see_incident(carlos, INC_LIMPIEZA) is False


def test_can_see_empleado_ve_sus_propios_reportes():
    ana = EMPLOYEES[1001]
    assert can_see_incident(ana, INC_MANTENIMIENTO) is True


def test_can_see_empleado_no_ve_reportes_ajenos():
    ana = EMPLOYEES[1001]
    assert can_see_incident(ana, INC_OTRA_PERSONA) is False


def test_can_see_gerente_ve_todo():
    alfredo = EMPLOYEES[3001]
    assert can_see_incident(alfredo, INC_LIMPIEZA) is True
    assert can_see_incident(alfredo, INC_OTRA_PERSONA) is True


# ---------------------------------------------------------------------------
# get_notification_recipients
# ---------------------------------------------------------------------------

def test_notification_mantenimiento_incluye_encargado_y_gerente():
    recipients = get_notification_recipients(INC_MANTENIMIENTO, EMPLOYEES)
    assert 2001 in recipients  # Carlos Enc (MANTENIMIENTO)
    assert 3001 in recipients  # Alfredo Gte
    assert 1001 not in recipients
    assert 2002 not in recipients


def test_notification_sin_encargado_solo_gerente():
    """Categoría no mapeada cae a GENERAL → ningún ENCARGADO tiene dept GENERAL."""
    recipients = get_notification_recipients(INC_SIN_CATEGORIA, EMPLOYEES)
    assert 3001 in recipients
    assert 2001 not in recipients
    assert 2002 not in recipients


# ---------------------------------------------------------------------------
# filter_visible_incidents
# ---------------------------------------------------------------------------

def test_filter_visible_incidents_encargado():
    carlos = EMPLOYEES[2001]
    incidents = [
        {"categoria": "MANTENIMIENTO", "employee_name": "Ana Empleada"},   # su dept
        {"categoria": "MANTENIMIENTO", "employee_name": "Otro"},            # su dept
        {"categoria": "LIMPIEZA", "employee_name": "Ana Empleada"},         # otro dept
        {"categoria": "RECEPCION", "employee_name": "James Smith"},         # otro dept
        {"categoria": "MANTENIMIENTO", "employee_name": "Andrei Popescu"},  # su dept
    ]
    visible = filter_visible_incidents(carlos, incidents)
    assert len(visible) == 3
    assert all(inc["categoria"] == "MANTENIMIENTO" for inc in visible)


# ---------------------------------------------------------------------------
# Bonus: employees.json parsea sin errores con la nueva estructura
# ---------------------------------------------------------------------------

def test_employees_json_parsea_correctamente():
    path = Path(__file__).parent.parent / "config" / "employees.json"
    data = json.loads(path.read_text())
    assert "employees" in data
    empleados = data["employees"]
    assert len(empleados) >= 1
    campos_obligatorios = {"telegram_id", "nombre", "departamento", "rol", "idioma"}
    for emp in empleados:
        assert campos_obligatorios <= emp.keys(), f"Faltan campos en {emp.get('nombre')}"
    roles = {e["rol"] for e in empleados}
    assert roles == {"EMPLEADO", "ENCARGADO", "GERENTE_GENERAL"}
    assert sum(1 for e in empleados if e["rol"] == "GERENTE_GENERAL") >= 1
    assert sum(1 for e in empleados if e["rol"] == "ENCARGADO") >= 3
