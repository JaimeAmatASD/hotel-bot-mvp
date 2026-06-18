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
    msg, _keyboard = format_notification_message(
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
    msg, _keyboard = format_notification_message(
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


# ---------------------------------------------------------------------------
# Tests 3-11: notify_incident (async, usa bot mock y storage mock)
# ---------------------------------------------------------------------------

INCIDENT_INCIDENCIA = {
    "id": 10,
    "tipo": "INCIDENCIA",
    "prioridad": "ALTA",
    "categoria": "MANTENIMIENTO",
    "subcategoria": None,
    "ubicacion": "Habitación 101",
    "descripcion": "Luz rota",
    "photo_path": None,
    "employee_name": "Ana",
    "employee_dept": "SPA",
}

INCIDENT_OBSERVACION = {
    "id": 11,
    "tipo": "OBSERVACION",
    "prioridad": None,
    "categoria": "LIMPIEZA",
    "subcategoria": None,
    "ubicacion": "Lobby",
    "descripcion": "Alfombra sucia",
    "photo_path": None,
    "employee_name": "Ana",
    "employee_dept": "SPA",
}


def make_bot():
    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock())
    bot.send_photo = AsyncMock(return_value=MagicMock())
    return bot


# Test 3: INCIDENCIA → llama send_notification_with_logging para encargado + gerente
@pytest.mark.asyncio
async def test_notify_incidencia_llama_encargado_y_gerente():
    from notifier import notify_incident
    bot = make_bot()
    with patch("notifier.storage.save_notification"), \
         patch("notifier.storage.get_notification_preferences", return_value={"mode": "todo", "excluded_departments": []}), \
         patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "off"):
        await notify_incident(bot=bot, incident=INCIDENT_INCIDENCIA, employees=EMPLOYEES, reporter_employee=REPORTER)

    assert bot.send_message.call_count == 2
    called_ids = {call.kwargs["chat_id"] for call in bot.send_message.call_args_list}
    assert 2001 in called_ids
    assert 3001 in called_ids


# Test 4: OBSERVACION → NO dispara notificaciones
@pytest.mark.asyncio
async def test_notify_observacion_no_notifica():
    from notifier import notify_incident
    bot = make_bot()
    with patch("notifier.storage.save_notification"), \
         patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "off"):
        await notify_incident(bot=bot, incident=INCIDENT_OBSERVACION, employees=EMPLOYEES, reporter_employee=REPORTER)

    assert bot.send_message.call_count == 0
    assert bot.send_photo.call_count == 0


# Test 5: redirect_mode=admin → usa ADMIN_TELEGRAM_ID
@pytest.mark.asyncio
async def test_notify_redirect_usa_admin_id():
    from notifier import notify_incident
    bot = make_bot()
    with patch("notifier.storage.save_notification"), \
         patch("notifier.storage.get_notification_preferences", return_value={"mode": "todo", "excluded_departments": []}), \
         patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "admin"), \
         patch("notifier.settings.ADMIN_TELEGRAM_ID", 9999):
        await notify_incident(bot=bot, incident=INCIDENT_INCIDENCIA, employees=EMPLOYEES, reporter_employee=REPORTER)

    for call in bot.send_message.call_args_list:
        assert call.kwargs["chat_id"] == 9999


# Test 6: Gerente mode=nada → NO recibe MEDIA
@pytest.mark.asyncio
async def test_gerente_modo_nada_no_recibe_media():
    from notifier import notify_incident
    bot = make_bot()
    incident_media = {**INCIDENT_INCIDENCIA, "prioridad": "MEDIA"}
    with patch("notifier.storage.save_notification"), \
         patch("notifier.storage.get_notification_preferences", return_value={"mode": "nada", "excluded_departments": []}), \
         patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "off"):
        await notify_incident(bot=bot, incident=incident_media, employees=EMPLOYEES, reporter_employee=REPORTER)

    called_ids = {call.kwargs["chat_id"] for call in bot.send_message.call_args_list}
    assert 2001 in called_ids
    assert 3001 not in called_ids


# Test 7: Gerente mode=nada → SÍ recibe CRITICA (excepción absoluta)
@pytest.mark.asyncio
async def test_gerente_modo_nada_si_recibe_critica():
    from notifier import notify_incident
    bot = make_bot()
    incident_critica = {**INCIDENT_INCIDENCIA, "prioridad": "CRITICA"}
    with patch("notifier.storage.save_notification"), \
         patch("notifier.storage.get_notification_preferences", return_value={"mode": "nada", "excluded_departments": []}), \
         patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "off"):
        await notify_incident(bot=bot, incident=incident_critica, employees=EMPLOYEES, reporter_employee=REPORTER)

    called_ids = {call.kwargs["chat_id"] for call in bot.send_message.call_args_list}
    assert 3001 in called_ids


# Test 8: Gerente mode=criticas → recibe ALTA y CRITICA, no MEDIA ni BAJA
@pytest.mark.asyncio
async def test_gerente_modo_criticas_filtra_por_prioridad():
    from notifier import notify_incident

    async def check_prioridad(prioridad, expect_gerente):
        bot = make_bot()
        inc = {**INCIDENT_INCIDENCIA, "prioridad": prioridad}
        with patch("notifier.storage.save_notification"), \
             patch("notifier.storage.get_notification_preferences", return_value={"mode": "criticas", "excluded_departments": []}), \
             patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "off"):
            await notify_incident(bot=bot, incident=inc, employees=EMPLOYEES, reporter_employee=REPORTER)
        called_ids = {call.kwargs["chat_id"] for call in bot.send_message.call_args_list}
        assert (3001 in called_ids) == expect_gerente, f"prioridad={prioridad}, expect_gerente={expect_gerente}"

    await check_prioridad("CRITICA", True)
    await check_prioridad("ALTA", True)
    await check_prioridad("MEDIA", False)
    await check_prioridad("BAJA", False)


# Test 9: Gerente con depto excluido → no recibe de ese depto (excepto CRITICA)
@pytest.mark.asyncio
async def test_gerente_depto_excluido_no_recibe_excepto_critica():
    from notifier import notify_incident

    bot = make_bot()
    with patch("notifier.storage.save_notification"), \
         patch("notifier.storage.get_notification_preferences",
               return_value={"mode": "todo", "excluded_departments": ["MANTENIMIENTO"]}), \
         patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "off"):
        await notify_incident(bot=bot, incident=INCIDENT_INCIDENCIA, employees=EMPLOYEES, reporter_employee=REPORTER)
    called_ids = {call.kwargs["chat_id"] for call in bot.send_message.call_args_list}
    assert 3001 not in called_ids

    bot2 = make_bot()
    incident_critica = {**INCIDENT_INCIDENCIA, "prioridad": "CRITICA"}
    with patch("notifier.storage.save_notification"), \
         patch("notifier.storage.get_notification_preferences",
               return_value={"mode": "todo", "excluded_departments": ["MANTENIMIENTO"]}), \
         patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "off"):
        await notify_incident(bot=bot2, incident=incident_critica, employees=EMPLOYEES, reporter_employee=REPORTER)
    called_ids2 = {call.kwargs["chat_id"] for call in bot2.send_message.call_args_list}
    assert 3001 in called_ids2


# Test 10: Encargado siempre recibe lo de su depto sin importar preferencias
@pytest.mark.asyncio
async def test_encargado_siempre_recibe_sin_filtros():
    from notifier import notify_incident
    bot = make_bot()
    with patch("notifier.storage.save_notification"), \
         patch("notifier.storage.get_notification_preferences", return_value={"mode": "nada", "excluded_departments": ["MANTENIMIENTO"]}), \
         patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "off"):
        await notify_incident(bot=bot, incident=INCIDENT_INCIDENCIA, employees=EMPLOYEES, reporter_employee=REPORTER)

    called_ids = {call.kwargs["chat_id"] for call in bot.send_message.call_args_list}
    assert 2001 in called_ids


# Test 11: Notificación fallida → registrada con status="failed" y error_message
@pytest.mark.asyncio
async def test_notificacion_fallida_se_registra_como_failed():
    from notifier import notify_incident
    bot = make_bot()
    bot.send_message = AsyncMock(side_effect=Exception("Telegram timeout"))

    saved_notifications = []

    with patch("notifier.storage.save_notification", side_effect=lambda **kw: saved_notifications.append(kw)), \
         patch("notifier.storage.get_notification_preferences", return_value={"mode": "todo", "excluded_departments": []}), \
         patch("notifier.settings.NOTIFICATION_REDIRECT_MODE", "off"):
        await notify_incident(bot=bot, incident=INCIDENT_INCIDENCIA, employees=EMPLOYEES, reporter_employee=REPORTER)

    failed = [n for n in saved_notifications if n.get("status") == "failed"]
    assert len(failed) >= 1
    assert failed[0]["error_message"] is not None
    assert "Telegram timeout" in failed[0]["error_message"]


# ---------------------------------------------------------------------------
# Work-order: notificación al asignado y a los managers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notify_assignee_envia_al_asignado():
    from notifier import notify_assignee
    employees = {222222222: {"telegram_id": 222222222, "nombre": "Andrei"}}
    incident = {"id": 7, "assigned_to_telegram_id": 222222222,
                "descripcion": "ventilador roto", "ubicacion": "Hab 77"}
    bot = MagicMock()
    sent = {}
    class FakeSender:
        async def send_text(self, chat_id, text): sent["chat"] = chat_id; sent["text"] = text
    with patch("notifier.state_change.as_sender", return_value=FakeSender()), \
         patch("notifier.state_change.settings") as s:
        s.NOTIFICATION_REDIRECT_MODE = "off"
        s.ADMIN_TELEGRAM_ID = 0
        await notify_assignee(bot=bot, incident=incident, employees=employees)
    assert sent["chat"] == 222222222
    assert "ventilador" in sent["text"].lower() or "tarea" in sent["text"].lower()


@pytest.mark.asyncio
async def test_notify_managers_resolved_avisa_a_managers():
    from notifier import notify_managers_resolved
    employees = {
        444444444: {"telegram_id": 444444444, "nombre": "Carlos", "departamento": "MANTENIMIENTO", "rol": "ENCARGADO"},
        777777777: {"telegram_id": 777777777, "nombre": "Alfredo", "departamento": "GENERAL", "rol": "GERENTE_GENERAL"},
    }
    incident = {"id": 7, "categoria": "MANTENIMIENTO", "descripcion": "x", "ubicacion": "Hab 77"}
    sent = []
    class FakeSender:
        async def send_text(self, chat_id, text): sent.append(chat_id)
    with patch("notifier.state_change.as_sender", return_value=FakeSender()), \
         patch("notifier.state_change.settings") as s:
        s.NOTIFICATION_REDIRECT_MODE = "off"
        s.ADMIN_TELEGRAM_ID = 0
        await notify_managers_resolved(bot=MagicMock(), incident=incident, actor_name="Andrei", employees=employees)
    assert 444444444 in sent and 777777777 in sent
