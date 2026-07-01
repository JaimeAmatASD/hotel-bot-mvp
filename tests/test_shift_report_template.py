"""Plantilla del informe de turno: render_shift_report.

Una sola función de formato reutilizada por el resumen previo, la notificación al
manager y /reporte REP-N. Incluye el bloque 'queda pendiente' para el handover.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import report_processor


def _items():
    return [
        {"tipo": "INCIDENCIA", "ubicacion": "Hab 47", "descripcion": "Ventilador roto",
         "prioridad": "ALTA", "estado": "CERRADA", "timestamp": "2026-06-25T08:10:00"},
        {"tipo": "INCIDENCIA", "ubicacion": "Lobby", "descripcion": "Luz parpadeando",
         "prioridad": "MEDIA", "estado": "EN_PROCESO", "timestamp": "2026-06-25T10:00:00"},
        {"tipo": "GUEST_INTEL", "ubicacion": "Hab 305", "descripcion": "Pidió almohadas extra",
         "estado": None, "timestamp": "2026-06-25T12:30:00"},
        {"tipo": "OBSERVACION", "ubicacion": "Depósito", "descripcion": "Falta stock de lámparas LED",
         "estado": None, "timestamp": "2026-06-25T15:45:00"},
    ]


def test_render_tiene_cabecera_y_secciones():
    text = report_processor.render_shift_report(
        _items(), display_id="REP-014", employee_name="Jaime A", department="MANTENIMIENTO")
    assert "INFORME DE TURNO — REP-014" in text
    assert "Jaime A" in text and "MANTENIMIENTO" in text
    assert "INCIDENCIAS (2)" in text
    assert "NOTAS DE HUÉSPED (1)" in text
    assert "NOVEDADES DEL TURNO (1)" in text
    # rango horario y total
    assert "08:10" in text and "15:45" in text
    assert "4 ítems" in text


def test_render_bloque_queda_pendiente_solo_abiertas():
    text = report_processor.render_shift_report(
        _items(), display_id="REP-014", employee_name="Jaime A", department="MANTENIMIENTO")
    assert "Handover: 1 pendiente" in text
    assert "QUEDA PENDIENTE" in text
    assert "Recibe seguimiento: MANTENIMIENTO" in text
    # La incidencia EN_PROCESO queda pendiente; la CERRADA no
    pend_section = text.split("QUEDA PENDIENTE")[1]
    assert "Luz parpadeando" in pend_section
    assert "Ventilador roto" not in pend_section


def test_render_omite_secciones_vacias_y_pendiente_si_todo_cerrado():
    items = [
        {"tipo": "INCIDENCIA", "ubicacion": "Hab 47", "descripcion": "Ventilador roto",
         "prioridad": "ALTA", "estado": "CERRADA", "timestamp": "2026-06-25T08:10:00"},
    ]
    text = report_processor.render_shift_report(
        items, display_id="REP-015", employee_name="Ana", department="SPA")
    assert "INCIDENCIAS (1)" in text
    assert "NOTAS DE HUÉSPED" not in text
    assert "NOVEDADES DEL TURNO" not in text
    assert "QUEDA PENDIENTE" not in text


def test_render_marca_contexto_de_huesped_en_incidencias_y_notas():
    items = [
        {"tipo": "INCIDENCIA", "ubicacion": "Hab 18", "descripcion": "Aire no enfría",
         "prioridad": "ALTA", "estado": "NUEVA", "huesped_afectado": 1,
         "habitacion_huesped": "18", "timestamp": "2026-06-25T09:00:00"},
        {"tipo": "GUEST_INTEL", "ubicacion": "Hab 22", "descripcion": "Prefiere almohada baja",
         "tipo_nota_huesped": "PREFERENCIA", "habitacion_huesped": "22",
         "timestamp": "2026-06-25T09:10:00"},
    ]
    text = report_processor.render_shift_report(
        items, display_id="REP-016", employee_name="Ana", department="RECEPCION")
    assert "huésped afectado" in text
    assert "huésped hab 18" in text
    assert "preferencia" in text
