"""Tests for the followup (missing critical field) flow (Sprint A.2)."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

EMPLOYEE = {"nombre": "Ana García", "departamento": "HOUSEKEEPING", "idioma": "es"}

BASE_META = {
    "_meta": {"input_type": "text", "transcription": None,
               "audio_language_detected": None, "audio_duration_seconds": None, "error": None}
}


def _result(tipo="INCIDENCIA", confianza=0.9, needs_followup=None, **kwargs):
    r = {
        "tipo": tipo, "ubicacion": "Habitación 301", "categoria": "MANTENIMIENTO",
        "subcategoria": None, "prioridad": "MEDIA", "descripcion": "Goteo en el baño",
        "idioma_original": "es", "huesped_afectado": False, "habitacion_huesped": None,
        "tipo_nota_huesped": None, "campos_faltantes": [], "confianza": confianza,
        **BASE_META, **kwargs,
    }
    if needs_followup:
        r["needs_followup"] = needs_followup
    return r


def make_update(text="hay un goteo en el baño"):
    update = MagicMock()
    update.message = AsyncMock()
    update.message.text = text
    update.message.voice = None
    update.message.audio = None
    update.effective_user = MagicMock(id=42)
    return update


def make_context(user_data=None):
    ctx = MagicMock()
    ctx.user_data = user_data or {}
    ctx.bot = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# Test 1 — Incidencia sin habitación → bot pide habitación
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_room_triggers_followup():
    """Bot pregunta por habitación y guarda awaiting_followup=True."""
    from handlers.text_handler import handle_text

    followup_result = _result(
        needs_followup={"field": "habitacion", "question": "¿En qué habitación?"},
        campos_faltantes=["habitacion"],
    )

    update = make_update("hay un goteo en el baño")
    ctx = make_context()

    with patch("handlers.text_handler.process_message", return_value=followup_result):
        await handle_text(update, ctx)

    # El bot debe haber preguntado por la habitación
    calls = [str(c) for c in update.message.reply_text.call_args_list]
    assert any("habitación" in c.lower() or "habitacion" in c.lower() for c in calls)

    # Estado correcto guardado
    assert ctx.user_data.get("awaiting_followup") is True
    assert "followup_started_at" in ctx.user_data
    assert ctx.user_data["pending"]["result"] == followup_result


# ---------------------------------------------------------------------------
# Test 2 — Respuesta al followup pasa previous_context al brain
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_followup_answer_sends_previous_context():
    """Al responder el followup, process_message recibe previous_context con el resultado original."""
    from handlers.text_handler import handle_text

    original_result = _result(campos_faltantes=["habitacion"],
                               needs_followup={"field": "habitacion", "question": "¿En qué habitación?"})
    resolved_result = _result(descripcion="Goteo en el baño, habitación 412",
                               ubicacion="Habitación 412")

    user_data = {
        "pending": {"result": original_result, "original_text": "hay un goteo en el baño"},
        "awaiting_followup": True,
        "followup_started_at": datetime.now().isoformat(),
    }
    update = make_update("412")
    ctx = make_context(user_data)

    with patch("handlers.text_handler.process_message", return_value=resolved_result) as mock_pm:
        await handle_text(update, ctx)

    mock_pm.assert_called_once()
    call_kwargs = mock_pm.call_args.kwargs
    assert call_kwargs["previous_context"] is not None
    assert call_kwargs["previous_context"]["result"] == original_result

    # Estado limpiado
    assert "awaiting_followup" not in ctx.user_data
    assert "followup_started_at" not in ctx.user_data


# ---------------------------------------------------------------------------
# Test 3 — Confianza baja → pide reformular, no guarda pending
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_low_confidence_asks_to_reformulate():
    """Confianza < 0.6: bot pide reformular y no guarda pending."""
    from handlers.text_handler import handle_text

    low_conf_result = _result(confianza=0.4)

    update = make_update("algo raro")
    ctx = make_context()

    with patch("handlers.text_handler.process_message", return_value=low_conf_result):
        await handle_text(update, ctx)

    # No se guarda pending
    assert "pending" not in ctx.user_data

    # El bot envió exactamente un mensaje (el de reformular)
    assert update.message.reply_text.call_count == 1
    msg = update.message.reply_text.call_args[0][0]
    assert "entendí" in msg.lower() or "contarme" in msg.lower()


# ---------------------------------------------------------------------------
# Test 4 — Confianza media → aviso ⚠️ pero sí muestra botones
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_medium_confidence_shows_warning_and_keyboard():
    """Confianza 0.6–0.8: resumen con ⚠️ y CONFIRM_KEYBOARD, sin preguntar extra."""
    from handlers.text_handler import handle_text

    mid_conf_result = _result(confianza=0.7)

    update = make_update("hay algo raro en la entrada")
    ctx = make_context()

    with patch("handlers.text_handler.process_message", return_value=mid_conf_result):
        await handle_text(update, ctx)

    # Debe haber guardado pending
    assert "pending" in ctx.user_data

    # El mensaje enviado debe contener ⚠️ y el keyboard de confirmación
    call_kwargs = update.message.reply_text.call_args[1]
    text_sent = update.message.reply_text.call_args[0][0]
    assert "⚠️" in text_sent
    assert call_kwargs.get("reply_markup") is not None
