"""Tests para Sprint B.2 — notificaciones."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Test 12: generate_display_id
# ---------------------------------------------------------------------------

def test_generate_display_id_incidencia():
    from storage import generate_display_id
    assert generate_display_id("INCIDENCIA", 1) == "INC-001"
    assert generate_display_id("INCIDENCIA", 42) == "INC-042"


def test_generate_display_id_otros_tipos():
    from storage import generate_display_id
    assert generate_display_id("OBSERVACION", 15) == "OBS-015"
    assert generate_display_id("GUEST_INTEL", 8) == "MEM-008"
    assert generate_display_id("NO_REPORTE", 3) == "NR-003"


# ---------------------------------------------------------------------------
# Fixtures compartidas
# ---------------------------------------------------------------------------

INCIDENT_MANT = {
    "id": 42,
    "tipo": "INCIDENCIA",
    "prioridad": "ALTA",
    "categoria": "MANTENIMIENTO",
    "subcategoria": "Sanitarios",
    "ubicacion": "Habitación 305",
    "descripcion": "Goteo en el baño",
    "photo_path": None,
    "employee_name": "Jaime A",
    "employee_dept": "SPA",
}

REPORTER = {"nombre": "Jaime A", "departamento": "SPA"}

EMPLOYEES = {
    1001: {"telegram_id": 1001, "nombre": "Ana", "departamento": "SPA", "rol": "EMPLEADO"},
    2001: {"telegram_id": 2001, "nombre": "Carlos Enc Mant", "departamento": "MANTENIMIENTO", "rol": "ENCARGADO"},
    3001: {"telegram_id": 3001, "nombre": "Alfredo Gerente", "departamento": "GENERAL", "rol": "GERENTE_GENERAL"},
}


# ---------------------------------------------------------------------------
# Test 1: format_notification_message sin redirect
# ---------------------------------------------------------------------------

def test_format_notification_sin_redirect():
    from notifier import format_notification_message
    msg = format_notification_message(
        incident=INCIDENT_MANT,
        reporter=REPORTER,
        incident_id_display="INC-042",
        is_redirect=False,
        actual_recipient_name=None,
    )
    assert "INC-042" in msg
    assert "🔔 Nueva incidencia" in msg
    assert "MANTENIMIENTO" in msg
    assert "ALTA" in msg
    assert "Habitación 305" in msg
    assert "Goteo en el baño" in msg
    assert "Jaime A" in msg
    assert "🧪" not in msg
    assert "Modo testing" not in msg


# ---------------------------------------------------------------------------
# Test 2: format_notification_message con redirect incluye prefijo
# ---------------------------------------------------------------------------

def test_format_notification_con_redirect():
    from notifier import format_notification_message
    msg = format_notification_message(
        incident=INCIDENT_MANT,
        reporter=REPORTER,
        incident_id_display="INC-042",
        is_redirect=True,
        actual_recipient_name="Carlos Enc Mant",
    )
    assert "🧪" in msg
    assert "Modo testing" in msg
    assert "Carlos Enc Mant" in msg
    assert "INC-042" in msg
    assert "MANTENIMIENTO" in msg
