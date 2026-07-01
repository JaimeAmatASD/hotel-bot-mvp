"""End-to-end hotel operation scenarios with fake Telegram/AI/SaaS edges.

These tests exercise the workflows a hotel team will validate manually:
employee reporting, manager visibility, department permissions, incident
actions, shift reports, and follow-up prompts.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import storage


async def _noop_async(*_args, **_kwargs):
    return True


EMP_HK = {
    "telegram_id": 101,
    "nombre": "María Housekeeping",
    "departamento": "HOUSEKEEPING",
    "idioma": "es",
    "rol": "EMPLEADO",
}
EMP_RECEPCION = {
    "telegram_id": 102,
    "nombre": "Lucía Recepción",
    "departamento": "RECEPCION",
    "idioma": "es",
    "rol": "EMPLEADO",
}
ENC_MANT = {
    "telegram_id": 201,
    "nombre": "Carlos Mantenimiento",
    "departamento": "MANTENIMIENTO",
    "idioma": "es",
    "rol": "ENCARGADO",
}
EMP_MANT = {
    "telegram_id": 203,
    "nombre": "Andrei Mantenimiento",
    "departamento": "MANTENIMIENTO",
    "idioma": "es",
    "rol": "EMPLEADO",
}
ENC_HK = {
    "telegram_id": 202,
    "nombre": "Ana Housekeeping",
    "departamento": "HOUSEKEEPING",
    "idioma": "es",
    "rol": "ENCARGADO",
}
GERENTE = {
    "telegram_id": 301,
    "nombre": "Alfredo Gerente",
    "departamento": "GENERAL",
    "idioma": "es",
    "rol": "GERENTE_GENERAL",
}

EMPLOYEES = {
    EMP_HK["telegram_id"]: EMP_HK,
    EMP_RECEPCION["telegram_id"]: EMP_RECEPCION,
    ENC_MANT["telegram_id"]: ENC_MANT,
    EMP_MANT["telegram_id"]: EMP_MANT,
    ENC_HK["telegram_id"]: ENC_HK,
    GERENTE["telegram_id"]: GERENTE,
}


INCIDENCIA_204 = {
    "tipo": "INCIDENCIA",
    "ubicacion": "Habitación 204",
    "categoria": "MANTENIMIENTO",
    "subcategoria": "Fontanería",
    "prioridad": "ALTA",
    "descripcion": "Agua saliendo del baño",
    "idioma_original": "es",
    "huesped_afectado": True,
    "habitacion_huesped": "204",
    "tipo_nota_huesped": None,
    "campos_faltantes": [],
    "confianza": 0.95,
    "_meta": {
        "input_type": "text",
        "transcription": None,
        "audio_language_detected": None,
        "audio_duration_seconds": None,
        "error": None,
        "photo_path": None,
    },
}


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    with patch.object(storage, "DB_PATH", tmp_path / "hotel_scenario.db"):
        storage.init_db()
        yield


def make_context(user_data: dict | None = None):
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    ctx.bot_data = {"employees": EMPLOYEES}
    ctx.args = []
    ctx.bot = AsyncMock()
    ctx.bot.send_message = AsyncMock()
    return ctx


def make_message_update(user_id: int, text: str = ""):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


def make_callback_update(user_id: int, data: str):
    query = MagicMock()
    query.data = data
    query.from_user.id = user_id
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.edit_message_caption = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()
    query.message = MagicMock()
    query.message.photo = None
    query.message.chat_id = user_id

    update = MagicMock()
    update.effective_user.id = user_id
    update.callback_query = query
    return update


def seed_classification(employee: dict, result: dict, message: str) -> int:
    return storage.save(employee, message, result)


def latest_reply_text(update) -> str:
    call = update.message.reply_text.call_args
    return call.args[0] if call and call.args else call.kwargs["text"]


@pytest.mark.asyncio
async def test_employee_report_confirm_and_manager_queries():
    """Employee reports an issue, confirms it, and the manager can find it."""
    from handlers.text_handler import handle_text
    from handlers.callback_handler import handle_callback
    from handlers.command_handler import handle_abiertas, handle_hab, handle_buscar

    context = make_context()
    report_update = make_message_update(EMP_HK["telegram_id"], "Hay agua saliendo del baño de la 204")

    with patch("handlers.text_handler.process_message", return_value=INCIDENCIA_204):
        await handle_text(report_update, context)

    assert context.user_data["pending"]["result"]["descripcion"] == "Agua saliendo del baño"
    assert "¿Es correcto?" in latest_reply_text(report_update)

    confirm_update = make_callback_update(EMP_HK["telegram_id"], "confirm")
    with patch("handlers.callback_handler.notifier.notify_incident", new=AsyncMock()) as notify_mock, \
         patch("handlers.callback_handler.sheets_sync.sync_incidencia", new=_noop_async):
        await handle_callback(confirm_update, context)

    notify_mock.assert_awaited_once()
    incident = storage.get_incident(1)
    assert incident["tipo"] == "INCIDENCIA"
    assert incident["ubicacion"] == "Habitación 204"
    assert incident["estado"] == "NUEVA"
    assert len(storage.get_events_for_incident(1)) == 1

    manager_ctx = make_context()

    abiertas_update = make_message_update(GERENTE["telegram_id"])
    await handle_abiertas(abiertas_update, manager_ctx)
    abiertas_text = latest_reply_text(abiertas_update)
    assert "INC-001" in abiertas_text
    assert "Habitación 204" in abiertas_text

    room_update = make_message_update(GERENTE["telegram_id"])
    manager_ctx.args = ["204"]
    await handle_hab(room_update, manager_ctx)
    assert "Agua saliendo del baño" in latest_reply_text(room_update)

    search_update = make_message_update(GERENTE["telegram_id"])
    manager_ctx.args = ["agua"]
    await handle_buscar(search_update, manager_ctx)
    assert "INC-001" in latest_reply_text(search_update)


@pytest.mark.asyncio
async def test_missing_location_asks_followup_without_saving():
    """An incomplete operational report should ask for the missing location."""
    from handlers.text_handler import handle_text

    result = {
        **INCIDENCIA_204,
        "ubicacion": "Habitación",
        "habitacion_huesped": None,
        "campos_faltantes": ["ubicacion"],
        "needs_followup": {"field": "ubicacion", "question": "¿Dónde exactamente?"},
    }
    context = make_context()
    update = make_message_update(EMP_HK["telegram_id"], "Hay una fuga en una habitación")

    with patch("handlers.text_handler.process_message", return_value=result):
        await handle_text(update, context)

    assert context.user_data["awaiting_followup"] is True
    assert latest_reply_text(update) == "¿Dónde exactamente?"
    assert storage.get_open_incidents() == []


@pytest.mark.asyncio
async def test_encargado_lifecycle_closes_incident_and_history_is_auditable():
    """Maintenance lead can take, progress and close a maintenance incident."""
    from handlers.callback_handler import _handle_incident_action
    from handlers.command_handler import handle_historial

    incident_id = seed_classification(EMP_HK, INCIDENCIA_204, "Hay agua saliendo del baño de la 204")
    storage.save_event(
        incident_id=incident_id,
        actor_telegram_id=EMP_HK["telegram_id"],
        actor_name=EMP_HK["nombre"],
        actor_role=EMP_HK["rol"],
        action="created",
        to_state="NUEVA",
    )

    context = make_context()
    with patch("handlers.callback_handler.notifier.notify_employee_state_change", new=AsyncMock()), \
         patch("handlers.callback_handler.notifier.notify_managers_resolved", new=AsyncMock()), \
         patch("handlers.callback_handler.sheets_sync.sync_incidencia", new=_noop_async):
        for action, expected_state in [
            ("tomar", "ASIGNADA"),
            ("comenzar", "EN_PROCESO"),
            ("terminado", "RESUELTA"),
            ("validar", "CERRADA"),
        ]:
            update = make_callback_update(ENC_MANT["telegram_id"], f"incident_action:{incident_id}:{action}")
            await _handle_incident_action(update.callback_query, context)
            assert storage.get_incident(incident_id)["estado"] == expected_state

    incident = storage.get_incident(incident_id)
    assert int(incident["assigned_to_telegram_id"]) == ENC_MANT["telegram_id"]
    assert incident["closed_at"] is not None

    events = storage.get_events_for_incident(incident_id)
    assert [e["action"] for e in events] == ["created", "tomar", "comenzar", "terminado", "validar"]

    history_update = make_message_update(GERENTE["telegram_id"])
    history_context = make_context()
    history_context.args = [f"INC-{incident_id}"]
    await handle_historial(history_update, history_context)
    history_text = latest_reply_text(history_update)
    assert "Historial INC-001" in history_text
    assert "Carlos" in history_text
    assert "Validada" in history_text


@pytest.mark.asyncio
async def test_delegation_full_lifecycle_and_reopen():
    """Encargado delega en un empleado; el empleado ejecuta; el encargado valida y puede reabrir."""
    from handlers.callback_handler import _handle_assign_to, _handle_incident_action

    incident_id = seed_classification(EMP_HK, INCIDENCIA_204, "Hay agua saliendo del baño de la 204")
    storage.save_event(
        incident_id=incident_id, actor_telegram_id=EMP_HK["telegram_id"],
        actor_name=EMP_HK["nombre"], actor_role=EMP_HK["rol"],
        action="created", to_state="NUEVA",
    )

    context = make_context()
    with patch("handlers.callback_handler.notifier.notify_employee_state_change", new=AsyncMock()), \
         patch("handlers.callback_handler.notifier.notify_managers_resolved", new=AsyncMock()), \
         patch("handlers.callback_handler.notifier.notify_assignee", new=AsyncMock()), \
         patch("handlers.callback_handler.sheets_sync.sync_incidencia", new=_noop_async):
        # 1) Encargado delega en Andrei
        upd = make_callback_update(ENC_MANT["telegram_id"], f"assign_to:{incident_id}:{EMP_MANT['telegram_id']}")
        await _handle_assign_to(upd.callback_query, context)
        inc = storage.get_incident(incident_id)
        assert inc["estado"] == "ASIGNADA"
        assert int(inc["assigned_to_telegram_id"]) == EMP_MANT["telegram_id"]
        assert int(inc["assigned_by"]) == ENC_MANT["telegram_id"]

        # 2) Andrei (empleado asignado) comienza y termina
        for action, expected in [("comenzar", "EN_PROCESO"), ("terminado", "RESUELTA")]:
            upd = make_callback_update(EMP_MANT["telegram_id"], f"incident_action:{incident_id}:{action}")
            await _handle_incident_action(upd.callback_query, context)
            assert storage.get_incident(incident_id)["estado"] == expected
        assert int(storage.get_incident(incident_id)["resolved_by"]) == EMP_MANT["telegram_id"]

        # 3) El encargado valida y cierra
        upd = make_callback_update(ENC_MANT["telegram_id"], f"incident_action:{incident_id}:validar")
        await _handle_incident_action(upd.callback_query, context)
        assert storage.get_incident(incident_id)["estado"] == "CERRADA"

        # 4) Reabrir desde RESUELTA no es posible (ya cerrada); reabrimos un caso resuelto fresco
        # Verificamos reabrir sobre una nueva incidencia llevada a RESUELTA
        iid2 = seed_classification(EMP_HK, INCIDENCIA_204, "Otra fuga")
        storage.update_incident_state_atomic(iid2, "ASIGNADA", ENC_MANT, ["NUEVA"],
                                             action="asignar", assignee_telegram_id=EMP_MANT["telegram_id"])
        storage.update_incident_state_atomic(iid2, "EN_PROCESO", EMP_MANT, ["ASIGNADA"], action="comenzar")
        storage.update_incident_state_atomic(iid2, "RESUELTA", EMP_MANT, ["EN_PROCESO"], action="terminado")
        upd = make_callback_update(ENC_MANT["telegram_id"], f"incident_action:{iid2}:reabrir")
        await _handle_incident_action(upd.callback_query, context)
        reopened = storage.get_incident(iid2)
        assert reopened["estado"] == "ASIGNADA"
        assert int(reopened["assigned_to_telegram_id"]) == EMP_MANT["telegram_id"]


@pytest.mark.asyncio
async def test_employee_terminates_directly_from_assigned():
    """El empleado puede saltarse 'comenzar' y marcar 'terminado' directo desde ASIGNADA."""
    from handlers.callback_handler import _handle_incident_action

    incident_id = seed_classification(EMP_HK, INCIDENCIA_204, "Fuga en la 204")
    storage.update_incident_state_atomic(incident_id, "ASIGNADA", ENC_MANT, ["NUEVA"],
                                         action="asignar", assignee_telegram_id=EMP_MANT["telegram_id"])

    context = make_context()
    with patch("handlers.callback_handler.notifier.notify_managers_resolved", new=AsyncMock()), \
         patch("handlers.callback_handler.notifier.notify_employee_state_change", new=AsyncMock()), \
         patch("handlers.callback_handler.sheets_sync.sync_incidencia", new=_noop_async):
        upd = make_callback_update(EMP_MANT["telegram_id"], f"incident_action:{incident_id}:terminado")
        await _handle_incident_action(upd.callback_query, context)

    inc = storage.get_incident(incident_id)
    assert inc["estado"] == "RESUELTA"
    assert int(inc["resolved_by"]) == EMP_MANT["telegram_id"]


@pytest.mark.asyncio
async def test_mistareas_lists_assigned_tasks_with_buttons():
    """/mistareas le muestra al empleado solo lo asignado a él, con botones de acción."""
    from handlers.command_handler import handle_mistareas

    # Una asignada a Andrei, otra a otra persona (no debe verla)
    mine = seed_classification(EMP_HK, INCIDENCIA_204, "Fuga mía en la 204")
    storage.update_incident_state_atomic(mine, "ASIGNADA", ENC_MANT, ["NUEVA"],
                                         action="asignar", assignee_telegram_id=EMP_MANT["telegram_id"])
    other = seed_classification(EMP_HK, INCIDENCIA_204, "Fuga ajena")
    storage.update_incident_state_atomic(other, "ASIGNADA", ENC_MANT, ["NUEVA"],
                                         action="asignar", assignee_telegram_id=ENC_MANT["telegram_id"])

    context = make_context()
    update = make_message_update(EMP_MANT["telegram_id"], "/mistareas")
    await handle_mistareas(update, context)

    # Primer reply = encabezado con el conteo; luego una tarjeta por tarea con teclado
    calls = update.message.reply_text.call_args_list
    header = calls[0].args[0] if calls[0].args else calls[0].kwargs["text"]
    assert "1 tarea" in header
    task_call = calls[1]
    kb = task_call.kwargs["reply_markup"]
    cbs = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert f"incident_action:{mine}:terminado" in cbs
    assert all(str(other) not in c.split(":")[1] for c in cbs)


@pytest.mark.asyncio
async def test_mistareas_empty_when_nothing_assigned():
    from handlers.command_handler import handle_mistareas
    context = make_context()
    update = make_message_update(EMP_MANT["telegram_id"], "/mistareas")
    await handle_mistareas(update, context)
    assert "No tenés tareas" in latest_reply_text(update)


@pytest.mark.asyncio
async def test_shift_report_compiles_template_and_notifies_dept_lead():
    """Turno: el empleado carga varias cosas → /reporte arma la plantilla → confirma →
    REP creado con ítems linkeados y aviso al encargado de su depto."""
    from handlers.command_handler import handle_reporte
    from handlers.callback_handler import handle_callback

    # María (HOUSEKEEPING) carga 3 cosas durante el turno
    seed_classification(EMP_HK, {"tipo": "INCIDENCIA", "ubicacion": "Hab 204",
        "categoria": "HOUSEKEEPING", "prioridad": "ALTA", "descripcion": "Toallas faltantes",
        "huesped_afectado": False, "campos_faltantes": [], "confianza": 0.9, "_meta": {}},
        "Faltan toallas en la 204")
    seed_classification(EMP_HK, {"tipo": "GUEST_INTEL", "ubicacion": "Hab 305",
        "descripcion": "Pidió almohadas extra", "campos_faltantes": [], "confianza": 0.9, "_meta": {}},
        "El de la 305 pidió almohadas")
    seed_classification(EMP_HK, {"tipo": "OBSERVACION", "ubicacion": "Pisos 2-4",
        "descripcion": "Revisé pisos 2 al 4, todo en orden", "campos_faltantes": [], "confianza": 0.9, "_meta": {}},
        "Revisé pisos 2 al 4 sin novedad")

    context = make_context()
    with patch("config.settings.NOTIFICATION_REDIRECT_MODE", "off"), \
         patch("handlers.callback_handler.sheets_sync.sync_reporte", new=_noop_async):
        # 1) /reporte arma el borrador con la plantilla
        rep_upd = make_message_update(EMP_HK["telegram_id"], "/reporte")
        await handle_reporte(rep_upd, context)
        summary = latest_reply_text(rep_upd)
        assert "INFORME DE TURNO" in summary
        assert "NOVEDADES DEL TURNO" in summary  # la observación narrativa entra acá
        assert context.user_data.get("pending_report_items")

        # 2) Confirmar → cierra el REP
        cb = make_callback_update(EMP_HK["telegram_id"], "report_confirm_all")
        await handle_callback(cb, context)

    # El REP quedó creado y los 3 ítems linkeados (ya no aparecen como sueltos)
    sueltos = storage.get_classifications_for_employee_recent(EMP_HK["nombre"], 24)
    assert sueltos == []
    # El encargado de HOUSEKEEPING recibió el informe
    sent_chats = [c.kwargs.get("chat_id") for c in context.bot.send_message.call_args_list]
    assert ENC_HK["telegram_id"] in sent_chats


@pytest.mark.asyncio
async def test_full_flow_report_assign_mistareas_terminate_porvalidar_validate():
    """Recorrido completo del flujo nuevo, de punta a punta:
    reportar → asignar → /mistareas → terminar → /porvalidar → validar → CERRADA.
    """
    from handlers.callback_handler import _handle_assign_to, _handle_incident_action
    from handlers.command_handler import handle_mistareas, handle_porvalidar

    context = make_context()
    patches = (
        patch("handlers.callback_handler.notifier.notify_assignee", new=AsyncMock()),
        patch("handlers.callback_handler.notifier.notify_employee_state_change", new=AsyncMock()),
        patch("handlers.callback_handler.notifier.notify_managers_resolved", new=AsyncMock()),
        patch("handlers.callback_handler.sheets_sync.sync_incidencia", new=_noop_async),
    )
    with patches[0], patches[1], patches[2], patches[3]:
        # 1) Un empleado reporta (queda NUEVA)
        incident_id = seed_classification(EMP_HK, INCIDENCIA_204, "Ventilador roto en la 204")
        storage.save_event(incident_id=incident_id, actor_telegram_id=EMP_HK["telegram_id"],
                           actor_name=EMP_HK["nombre"], actor_role=EMP_HK["rol"],
                           action="created", to_state="NUEVA")
        assert storage.get_incident(incident_id)["estado"] == "NUEVA"

        # 2) El encargado de mantenimiento se la asigna a Andrei
        upd = make_callback_update(ENC_MANT["telegram_id"], f"assign_to:{incident_id}:{EMP_MANT['telegram_id']}")
        await _handle_assign_to(upd.callback_query, context)
        assert storage.get_incident(incident_id)["estado"] == "ASIGNADA"

        # 3) Andrei la ve en /mistareas con botón para terminar
        mt = make_message_update(EMP_MANT["telegram_id"], "/mistareas")
        await handle_mistareas(mt, context)
        mis_cbs = [b.callback_data for row in mt.message.reply_text.call_args_list[1].kwargs["reply_markup"].inline_keyboard for b in row]
        assert f"incident_action:{incident_id}:terminado" in mis_cbs

        # 4) Andrei termina directo (sin pasar por "comenzar")
        upd = make_callback_update(EMP_MANT["telegram_id"], f"incident_action:{incident_id}:terminado")
        await _handle_incident_action(upd.callback_query, context)
        assert storage.get_incident(incident_id)["estado"] == "RESUELTA"

        # 5) El encargado la ve en /porvalidar con botones de validar/reabrir
        pv = make_message_update(ENC_MANT["telegram_id"], "/porvalidar")
        await handle_porvalidar(pv, context)
        pv_cbs = [b.callback_data for row in pv.message.reply_text.call_args_list[1].kwargs["reply_markup"].inline_keyboard for b in row]
        assert f"incident_action:{incident_id}:validar" in pv_cbs
        assert f"incident_action:{incident_id}:reabrir" in pv_cbs

        # 6) El encargado valida y cierra
        upd = make_callback_update(ENC_MANT["telegram_id"], f"incident_action:{incident_id}:validar")
        await _handle_incident_action(upd.callback_query, context)
        final = storage.get_incident(incident_id)
        assert final["estado"] == "CERRADA"
        assert int(final["closed_by"]) == ENC_MANT["telegram_id"]

        # 7) Ya no aparece en /porvalidar
        pv2 = make_message_update(ENC_MANT["telegram_id"], "/porvalidar")
        await handle_porvalidar(pv2, context)
        assert "No hay" in latest_reply_text(pv2)


@pytest.mark.asyncio
async def test_porvalidar_lists_resolved_with_buttons_for_manager():
    """/porvalidar le muestra al encargado las RESUELTA de su depto, con botones de validar."""
    from handlers.command_handler import handle_porvalidar

    # Una RESUELTA de MANTENIMIENTO (la ve el encargado de mant) y una ASIGNADA (no aparece)
    resuelta = seed_classification(EMP_HK, INCIDENCIA_204, "Fuga resuelta 204")
    storage.update_incident_state_atomic(resuelta, "ASIGNADA", ENC_MANT, ["NUEVA"],
                                         action="asignar", assignee_telegram_id=EMP_MANT["telegram_id"])
    storage.update_incident_state_atomic(resuelta, "RESUELTA", EMP_MANT, ["ASIGNADA", "EN_PROCESO"],
                                         action="terminado")
    asignada = seed_classification(EMP_HK, INCIDENCIA_204, "Otra en curso")
    storage.update_incident_state_atomic(asignada, "ASIGNADA", ENC_MANT, ["NUEVA"],
                                         action="asignar", assignee_telegram_id=EMP_MANT["telegram_id"])

    context = make_context()
    update = make_message_update(ENC_MANT["telegram_id"], "/porvalidar")
    await handle_porvalidar(update, context)

    calls = update.message.reply_text.call_args_list
    header = calls[0].args[0] if calls[0].args else calls[0].kwargs["text"]
    assert "1" in header
    kb = calls[1].kwargs["reply_markup"]
    cbs = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert f"incident_action:{resuelta}:validar" in cbs
    assert f"incident_action:{resuelta}:reabrir" in cbs
    # La ASIGNADA no debe aparecer
    assert all(str(asignada) not in c.split(":")[1] for c in cbs)


@pytest.mark.asyncio
async def test_porvalidar_encargado_no_ve_otro_departamento():
    from handlers.command_handler import handle_porvalidar

    # RESUELTA de MANTENIMIENTO: el encargado de HOUSEKEEPING no la ve
    resuelta = seed_classification(EMP_HK, INCIDENCIA_204, "Fuga mant")
    storage.update_incident_state_atomic(resuelta, "ASIGNADA", ENC_MANT, ["NUEVA"],
                                         action="asignar", assignee_telegram_id=EMP_MANT["telegram_id"])
    storage.update_incident_state_atomic(resuelta, "RESUELTA", EMP_MANT, ["ASIGNADA", "EN_PROCESO"],
                                         action="terminado")

    context = make_context()
    update = make_message_update(ENC_HK["telegram_id"], "/porvalidar")
    await handle_porvalidar(update, context)
    assert "No hay" in latest_reply_text(update)


@pytest.mark.asyncio
async def test_porvalidar_empleado_rechazado():
    from handlers.command_handler import handle_porvalidar
    context = make_context()
    update = make_message_update(EMP_MANT["telegram_id"], "/porvalidar")
    await handle_porvalidar(update, context)
    txt = latest_reply_text(update).lower()
    assert "encargado" in txt or "gerente" in txt


@pytest.mark.asyncio
async def test_assigned_employee_only_can_act_on_own_incident():
    """Un empleado no puede ejecutar acciones sobre una incidencia asignada a otro."""
    from handlers.callback_handler import _handle_incident_action

    incident_id = seed_classification(EMP_HK, INCIDENCIA_204, "Fuga en la 204")
    storage.update_incident_state_atomic(incident_id, "ASIGNADA", ENC_MANT, ["NUEVA"],
                                         action="asignar", assignee_telegram_id=ENC_MANT["telegram_id"])

    context = make_context()
    upd = make_callback_update(EMP_MANT["telegram_id"], f"incident_action:{incident_id}:comenzar")
    await _handle_incident_action(upd.callback_query, context)

    upd.callback_query.answer.assert_awaited()
    assert "permiso" in upd.callback_query.answer.call_args.args[0].lower()
    assert storage.get_incident(incident_id)["estado"] == "ASIGNADA"


@pytest.mark.asyncio
async def test_wrong_department_encargado_cannot_take_maintenance_incident():
    """Housekeeping lead must not be able to act on maintenance work orders."""
    from handlers.callback_handler import _handle_incident_action

    incident_id = seed_classification(EMP_HK, INCIDENCIA_204, "Fuga en la 204")
    context = make_context()
    update = make_callback_update(ENC_HK["telegram_id"], f"incident_action:{incident_id}:tomar")

    await _handle_incident_action(update.callback_query, context)

    update.callback_query.answer.assert_awaited_once()
    answer_text = update.callback_query.answer.call_args.args[0]
    assert "permisos" in answer_text.lower()
    assert storage.get_incident(incident_id)["estado"] == "NUEVA"
    events = storage.get_events_for_incident(incident_id)
    assert events[0]["action"] == "action_rejected_no_permission"


@pytest.mark.asyncio
async def test_shift_report_links_items_and_manager_can_open_report():
    """End-of-shift report links recent items and remains queryable."""
    from handlers.command_handler import handle_reporte
    from handlers.callback_handler import handle_callback

    guest_intel = {
        **INCIDENCIA_204,
        "tipo": "GUEST_INTEL",
        "categoria": "RECEPCION",
        "prioridad": None,
        "ubicacion": "Habitación 305",
        "descripcion": "Huésped de la 305 es alérgico a frutos secos",
        "habitacion_huesped": "305",
        "tipo_nota_huesped": "ALERGIA",
    }
    observation = {
        **INCIDENCIA_204,
        "tipo": "OBSERVACION",
        "categoria": "LIMPIEZA",
        "prioridad": None,
        "ubicacion": "Lobby",
        "descripcion": "La alfombra del lobby se ensucia repetidamente",
        "habitacion_huesped": None,
        "huesped_afectado": None,
    }
    seed_classification(EMP_HK, INCIDENCIA_204, "Agua en la 204")
    seed_classification(EMP_HK, guest_intel, "El huésped 305 es alérgico")
    seed_classification(EMP_HK, observation, "La alfombra del lobby se ensucia mucho")

    employee_context = make_context()
    report_update = make_message_update(EMP_HK["telegram_id"])
    await handle_reporte(report_update, employee_context)

    assert len(employee_context.user_data["pending_report_items"]["items"]) == 3
    assert "INFORME DE TURNO" in latest_reply_text(report_update)

    confirm_update = make_callback_update(EMP_HK["telegram_id"], "report_confirm_all")
    with patch("handlers.callback_handler.report_processor.notify_manager_report", new=AsyncMock()) as notify_report, \
         patch("handlers.callback_handler.sheets_sync.sync_reporte", new=_noop_async):
        await handle_callback(confirm_update, employee_context)

    notify_report.assert_awaited_once()
    report = storage.get_report_with_items(1)
    assert report["status"] == "CLOSED"
    assert len(report["items"]) == 3
    assert all(item["report_id"] == 1 for item in report["items"])

    manager_update = make_message_update(GERENTE["telegram_id"])
    manager_context = make_context()
    manager_context.args = ["REP-1"]
    await handle_reporte(manager_update, manager_context)
    report_text = latest_reply_text(manager_update)
    assert "REP-001" in report_text
    assert "3 ítems" in report_text


@pytest.mark.asyncio
async def test_employee_cannot_read_other_employee_incident_history():
    """Front-line employees should not see incidents reported by other staff."""
    from handlers.command_handler import handle_historial

    incident_id = seed_classification(EMP_HK, INCIDENCIA_204, "Fuga en la 204")
    storage.save_event(
        incident_id=incident_id,
        actor_telegram_id=EMP_HK["telegram_id"],
        actor_name=EMP_HK["nombre"],
        actor_role=EMP_HK["rol"],
        action="created",
        to_state="NUEVA",
    )

    update = make_message_update(EMP_RECEPCION["telegram_id"])
    context = make_context()
    context.args = [str(incident_id)]

    await handle_historial(update, context)

    assert latest_reply_text(update) == "No tenés permiso para ver esa incidencia."


@pytest.mark.asyncio
async def test_sector_rollup_combines_types_and_gerente_gated(monkeypatch):
    """Varios ítems del sector → /reporte sector muestra el combinado; con el flag
    off el gerente no recibe el informe per-persona por el bot."""
    from handlers.command_handler import handle_reporte
    from handlers.callback_handler import handle_callback

    monkeypatch.setattr("report_processor.settings.REPORT_NOTIFY_GERENTE", False)

    # EMP_MANT carga tres ítems: INCIDENCIA (abierta), OBSERVACION, GUEST_INTEL
    seed_classification(
        EMP_MANT,
        {"tipo": "INCIDENCIA", "prioridad": "ALTA", "categoria": "MANTENIMIENTO",
         "ubicacion": "Hab 8", "descripcion": "baño roto"},
        "baño roto en Hab 8",
    )
    seed_classification(
        EMP_MANT,
        {"tipo": "OBSERVACION", "ubicacion": "Pisos", "descripcion": "ronda sin novedad"},
        "ronda sin novedad",
    )
    seed_classification(
        EMP_MANT,
        {"tipo": "GUEST_INTEL", "ubicacion": "Hab 45", "descripcion": "huésped pide toallas"},
        "huésped pide toallas",
    )

    # 1. ENC_MANT pide el rollup del sector → debe ver los tres ítems y el bloque ABIERTAS
    enc_ctx = make_context()
    enc_ctx.args = ["sector"]
    upd = make_message_update(ENC_MANT["telegram_id"], "/reporte sector")
    await handle_reporte(upd, enc_ctx)
    text = latest_reply_text(upd)
    assert "ESTADO DEL SECTOR — MANTENIMIENTO" in text
    assert "baño roto" in text
    assert "ronda sin novedad" in text
    assert "huésped pide toallas" in text
    assert "ABIERTAS EN EL SECTOR" in text  # la INCIDENCIA en estado NUEVA

    # 2. Con REPORT_NOTIFY_GERENTE=False, el gerente no recibe el informe de turno
    # Ponemos al gerente en modo "todo" para que, si el flag estuviera on, sí recibiría
    storage.set_notification_mode(GERENTE["telegram_id"], "todo")
    emp_ctx = make_context()
    rep_upd = make_message_update(EMP_MANT["telegram_id"], "/reporte")
    with patch("config.settings.NOTIFICATION_REDIRECT_MODE", "off"), \
         patch("handlers.callback_handler.sheets_sync.sync_reporte", new=_noop_async):
        await handle_reporte(rep_upd, emp_ctx)
        cb = make_callback_update(EMP_MANT["telegram_id"], "report_confirm_all")
        await handle_callback(cb, emp_ctx)

    sent_chats = [c.kwargs.get("chat_id") for c in emp_ctx.bot.send_message.call_args_list]
    assert ENC_MANT["telegram_id"] in sent_chats    # encargado del depto siempre recibe
    assert GERENTE["telegram_id"] not in sent_chats  # gerente bloqueado por REPORT_NOTIFY_GERENTE=False
