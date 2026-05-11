"""Tests for the correction state flow (Sprint A.1)."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EMPLOYEE = {"nombre": "Ana García", "departamento": "HOUSEKEEPING", "idioma": "es"}

FIRST_RESULT = {
    "tipo": "INCIDENCIA",
    "ubicacion": "habitación 301",
    "categoria": "LIMPIEZA",
    "subcategoria": None,
    "prioridad": "MEDIA",
    "descripcion": "Habitación sucia",
    "idioma_original": "es",
    "huesped_afectado": False,
    "habitacion_huesped": None,
    "tipo_nota_huesped": None,
    "campos_faltantes": [],
    "confianza": 0.8,
    "_meta": {"input_type": "text", "transcription": None,
               "audio_language_detected": None, "audio_duration_seconds": None, "error": None},
}

CORRECTED_RESULT = {**FIRST_RESULT, "descripcion": "Habitación 301 sin toallas", "confianza": 0.95}


def make_update(text=None):
    update = MagicMock()
    update.message = AsyncMock()
    update.message.text = text
    update.message.voice = None
    update.message.audio = None
    update.callback_query = AsyncMock()
    update.callback_query.data = "correct"
    update.effective_user = MagicMock(id=42)
    return update


def make_context(user_data=None):
    ctx = MagicMock()
    ctx.user_data = user_data or {}
    ctx.bot = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# Test 1 — Happy path: texto → Corregir → corrección por texto
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_text_correction_happy_path():
    """Corrección por texto: classify recibe previous_context con el resultado original."""
    from handlers.text_handler import handle_text

    # Estado después de que el usuario pulsó "Corregir"
    user_data = {
        "pending": {"result": FIRST_RESULT, "original_text": "habitación sucia"},
        "awaiting_correction": True,
        "correction_started_at": datetime.now().isoformat(),
    }
    update = make_update(text="sin toallas en el baño")
    ctx = make_context(user_data)

    with patch("handlers.text_handler.process_message", return_value=CORRECTED_RESULT) as mock_pm:
        await handle_text(update, ctx)

    mock_pm.assert_called_once()
    call_kwargs = mock_pm.call_args.kwargs
    assert call_kwargs["previous_context"] is not None
    assert call_kwargs["previous_context"]["original_text"] == "habitación sucia"
    assert call_kwargs["previous_context"]["result"]["tipo"] == "INCIDENCIA"

    # El nuevo pending debe contener el resultado corregido
    assert ctx.user_data["pending"]["result"]["descripcion"] == "Habitación 301 sin toallas"

    # El estado de corrección debe haberse limpiado
    assert "awaiting_correction" not in ctx.user_data
    assert "correction_started_at" not in ctx.user_data


# ---------------------------------------------------------------------------
# Test 2 — Timeout: corrección expirada → procesa como mensaje nuevo
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_text_correction_timeout():
    """Corrección expirada: classify recibe previous_context=None y se avisa al usuario."""
    from handlers.text_handler import handle_text

    expired_time = (datetime.now() - timedelta(minutes=6)).isoformat()
    user_data = {
        "pending": {"result": FIRST_RESULT, "original_text": "habitación sucia"},
        "awaiting_correction": True,
        "correction_started_at": expired_time,
    }
    update = make_update(text="sin toallas en el baño")
    ctx = make_context(user_data)

    with patch("handlers.text_handler.process_message", return_value=CORRECTED_RESULT) as mock_pm:
        await handle_text(update, ctx)

    mock_pm.assert_called_once()
    call_kwargs = mock_pm.call_args.kwargs
    # Sin previous_context porque expiró
    assert call_kwargs["previous_context"] is None

    # El bot debe haber avisado del timeout
    timeout_call = any(
        "tiempo" in str(call).lower()
        for call in update.message.reply_text.call_args_list
    )
    assert timeout_call, "El bot debería avisar que el tiempo de corrección expiró"

    # El estado de corrección debe haberse limpiado
    assert "awaiting_correction" not in ctx.user_data


# ---------------------------------------------------------------------------
# Test 3 — Corrección por audio
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audio_correction_happy_path():
    """Corrección por audio: classify recibe previous_context con el resultado original."""
    from handlers.audio_handler import handle_audio

    user_data = {
        "pending": {"result": FIRST_RESULT, "original_text": "habitación sucia"},
        "awaiting_correction": True,
        "correction_started_at": datetime.now().isoformat(),
    }

    update = make_update()
    update.message.voice = MagicMock(file_id="fake_file_id")

    ctx = make_context(user_data)
    ctx.bot.get_file = AsyncMock(return_value=AsyncMock(
        download_to_drive=AsyncMock()
    ))

    audio_result = {**CORRECTED_RESULT,
                    "_meta": {"input_type": "audio", "transcription": "sin toallas en el baño",
                               "audio_language_detected": "es", "audio_duration_seconds": 3.0, "error": None}}

    with patch("handlers.audio_handler.process_message", return_value=audio_result) as mock_pm, \
         patch("os.unlink"):
        await handle_audio(update, ctx)

    mock_pm.assert_called_once()
    call_kwargs = mock_pm.call_args.kwargs
    assert call_kwargs["previous_context"] is not None
    assert call_kwargs["previous_context"]["original_text"] == "habitación sucia"
    assert call_kwargs["is_audio"] is True

    # Estado de corrección limpiado
    assert "awaiting_correction" not in ctx.user_data
