"""Tests for domain entity converters and helpers."""
from domain.entities import Employee, Incident
from config.enums import IncidentState, Role


class TestEmployee:
    def test_from_dict_with_full_payload(self):
        emp = Employee.from_dict({
            "telegram_id": 12345,
            "nombre": "Carlos Encargado Mant",
            "departamento": "MANTENIMIENTO",
            "idioma": "es",
            "rol": "ENCARGADO",
        })
        assert emp.telegram_id == 12345
        assert emp.nombre == "Carlos Encargado Mant"
        assert emp.rol == Role.ENCARGADO

    def test_from_dict_defaults_role_to_empleado(self):
        emp = Employee.from_dict({
            "telegram_id": 1,
            "nombre": "Sin Rol",
            "departamento": "HK",
            "idioma": "es",
        })
        assert emp.rol == Role.EMPLEADO

    def test_first_name(self):
        emp = Employee(telegram_id=1, nombre="María García", departamento="HK")
        assert emp.first_name == "María"

    def test_first_name_empty_when_no_name(self):
        emp = Employee(telegram_id=1, nombre="", departamento="HK")
        assert emp.first_name == ""

    def test_is_manager(self):
        assert Employee(1, "X", "Y", rol=Role.GERENTE_GENERAL).is_manager()
        assert Employee(1, "X", "Y", rol=Role.ENCARGADO).is_manager()
        assert not Employee(1, "X", "Y", rol=Role.EMPLEADO).is_manager()

    def test_round_trip_dict(self):
        original = {
            "telegram_id": 1, "nombre": "X", "departamento": "HK",
            "idioma": "es", "rol": "GERENTE_GENERAL",
        }
        assert Employee.from_dict(original).to_dict() == original


class TestIncident:
    def test_from_row_basic(self):
        row = {
            "id": 42, "timestamp": "2026-05-27T10:00:00",
            "employee_name": "Ana", "employee_dept": "HK",
            "descripcion": "Baño roto", "ubicacion": "Habitación 305",
            "categoria": "MANTENIMIENTO", "prioridad": "ALTA",
            "estado": "NUEVA",
        }
        inc = Incident.from_row(row)
        assert inc.id == 42
        assert inc.estado == IncidentState.NUEVA
        assert inc.descripcion == "Baño roto"

    def test_from_row_defaults_estado_when_missing(self):
        inc = Incident.from_row({"id": 1, "timestamp": "", "employee_name": "X", "descripcion": ""})
        assert inc.estado == IncidentState.NUEVA

    def test_is_open(self):
        inc = Incident(id=1, timestamp="", employee_name="X", descripcion="")
        assert inc.is_open()
        inc.estado = IncidentState.CERRADA
        assert not inc.is_open()

    def test_is_assigned(self):
        inc = Incident(id=1, timestamp="", employee_name="X", descripcion="")
        assert not inc.is_assigned()
        inc.assigned_to_telegram_id = 999
        assert inc.is_assigned()

    def test_huesped_afectado_coerced_to_bool(self):
        inc = Incident.from_row({"id": 1, "timestamp": "", "employee_name": "X",
                                 "descripcion": "", "huesped_afectado": 1})
        assert inc.huesped_afectado is True
        inc2 = Incident.from_row({"id": 2, "timestamp": "", "employee_name": "X",
                                  "descripcion": "", "huesped_afectado": 0})
        assert inc2.huesped_afectado is False
