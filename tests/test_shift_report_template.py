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
    assert "QUEDA PENDIENTE (1)" in text
    # La incidencia EN_PROCESO queda pendiente; la CERRADA no
    pend_section = text.split("QUEDA PENDIENTE")[1].split("INCIDENCIAS")[0]
    assert "Luz parpadeando" in pend_section
    assert "Ventilador roto" not in pend_section


def test_render_pone_los_pendientes_antes_del_detalle():
    """Lo que falta se lee primero; es la razón de ser del informe."""
    text = report_processor.render_shift_report(
        _items(), display_id="REP-014", employee_name="Jaime A", department="MANTENIMIENTO")
    assert text.index("QUEDA PENDIENTE") < text.index("INCIDENCIAS (2)")


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


# --- Pendientes arriba, arrastre acotado y truncado (sprint C.1) ---

def _item(**kw):
    base = {"id": 1, "timestamp": "2026-08-09T10:00:00", "tipo": "INCIDENCIA",
            "estado": "NUEVA", "ubicacion": "Habitación 204", "descripcion": "Pierde agua",
            "prioridad": "ALTA"}
    base.update(kw)
    return base


def _render(items, carryover=()):
    return report_processor.render_shift_report(
        items, display_id="REP-012", employee_name="Jaime A",
        department="MANTENIMIENTO", carryover=carryover)


def test_pendientes_go_before_the_detail():
    """Lo que falta se lee primero; es la razón de ser del informe."""
    texto = _render([_item(descripcion="abierta")])
    assert texto.index("QUEDA PENDIENTE") < texto.index("INCIDENCIAS (1)")


def test_pendiente_line_carries_actionable_id():
    texto = _render([_item(id=18, descripcion="abierta")])
    assert "INC-018" in texto


def test_carryover_is_marked_with_its_date():
    viejo = _item(id=18, timestamp="2026-07-02T10:00:00", descripcion="cerradura")
    texto = _render([], carryover=[viejo])
    assert "↩ 02/07" in texto
    assert "QUEDA PENDIENTE (1)" in texto


def test_items_of_the_day_are_not_marked_as_carryover():
    texto = _render([_item(descripcion="de hoy")])
    assert "↩" not in texto


def test_closed_items_are_not_pendientes():
    texto = _render([_item(estado="CERRADA"), _item(estado="CANCELADA")])
    assert "QUEDA PENDIENTE" not in texto


def test_long_descriptions_are_truncated():
    largo = "x" * 200
    texto = _render([_item(descripcion=largo)])
    assert "x" * 200 not in texto
    assert "…" in texto


def test_room_labels_are_shortened():
    texto = _render([_item(ubicacion="Habitación 204")])
    assert "Hab 204" in texto
    assert "Habitación 204" not in texto


def test_no_pendientes_section_when_everything_is_closed():
    texto = _render([_item(estado="CERRADA")])
    assert "QUEDA PENDIENTE" not in texto
    assert "INCIDENCIAS (1)" in texto


def test_carryover_is_capped_with_a_counter():
    """13 pendientes no pueden sepultar el informe de hoy."""
    viejos = [_item(id=n, timestamp=f"2026-07-{n:02d}T10:00:00", descripcion=f"vieja {n}")
              for n in range(1, 14)]
    texto = _render([], carryover=viejos)

    assert "QUEDA PENDIENTE (13)" in texto, "el total real se sigue diciendo"
    assert texto.count("↩") == report_processor._MAX_CARRYOVER
    assert "y 8 más abiertas" in texto
    assert "/abiertas" in texto


def test_contador_de_una_sola_oculta_va_en_singular():
    viejos = [_item(id=n, timestamp=f"2026-07-{n:02d}T10:00:00") for n in range(1, 7)]
    texto = _render([], carryover=viejos)
    assert "y 1 más abierta ·" in texto


def test_carryover_under_the_cap_has_no_counter():
    viejos = [_item(id=n, timestamp=f"2026-07-{n:02d}T10:00:00") for n in range(1, 4)]
    texto = _render([], carryover=viejos)
    assert "más abiertas" not in texto


def test_carryover_shows_the_oldest_first():
    viejos = [_item(id=n, timestamp=f"2026-07-{n:02d}T10:00:00", descripcion=f"vieja {n}")
              for n in range(1, 14)]
    texto = _render([], carryover=viejos)
    assert "vieja 1" in texto, "la más vieja tiene que estar"
    assert "vieja 13" not in texto, "la más nueva es la que se corta"
