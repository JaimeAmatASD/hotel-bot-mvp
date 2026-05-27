"""Tests for debug mode (Sprint A.2.5)."""
import sqlite3
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

EMPLOYEE = {"nombre": "Ana García", "departamento": "HOUSEKEEPING", "idioma": "es"}

BASE_RESULT = {
    "tipo": "INCIDENCIA", "ubicacion": "Habitación 301", "categoria": "MANTENIMIENTO",
    "subcategoria": "Sanitarios", "prioridad": "MEDIA", "descripcion": "Baño roto",
    "idioma_original": "es", "huesped_afectado": False, "habitacion_huesped": None,
    "tipo_nota_huesped": None, "campos_faltantes": [], "confianza": 0.9,
    "_meta": {"input_type": "text", "transcription": None,
               "audio_language_detected": None, "audio_duration_seconds": None, "error": None},
}


def make_update(text="baño roto en habitación 301", user_id=42):
    update = MagicMock()
    update.message = AsyncMock()
    update.message.text = text
    update.message.voice = None
    update.message.audio = None
    update.effective_user = MagicMock(id=user_id)
    return update


def make_context():
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.bot = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# Test 1 — Default off: usuario nuevo no ve bloque debug
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_debug_off_by_default():
    from handlers.text_handler import handle_text

    update = make_update(user_id=100)
    ctx = make_context()

    with patch("handlers.text_handler.process_message", return_value=BASE_RESULT), \
         patch("handlers._flow.get_debug_mode", return_value=False):
        await handle_text(update, ctx)

    text_sent = update.message.reply_text.call_args[0][0]
    assert "🔍" not in text_sent
    assert "Detalles técnicos" not in text_sent


# ---------------------------------------------------------------------------
# Test 2 — Debug on: usuario con debug activado ve bloque debug
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_debug_on_shows_block():
    from handlers.text_handler import handle_text

    update = make_update(user_id=101)
    ctx = make_context()

    with patch("handlers.text_handler.process_message", return_value=BASE_RESULT), \
         patch("handlers._flow.get_debug_mode", return_value=True):
        await handle_text(update, ctx)

    text_sent = update.message.reply_text.call_args[0][0]
    assert "🔍" in text_sent
    assert "Detalles técnicos" in text_sent
    assert "Confianza: 90%" in text_sent
    assert "Campos faltantes: ninguno" in text_sent


# ---------------------------------------------------------------------------
# Test 3 — Persistencia en SQLite: set/get round-trip
# ---------------------------------------------------------------------------

def test_debug_mode_sqlite_persistence(tmp_path, monkeypatch):
    import storage

    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "test.db")
    storage.init_db()

    assert storage.get_debug_mode(999) is False

    storage.set_debug_mode(999, True)
    assert storage.get_debug_mode(999) is True

    storage.set_debug_mode(999, False)
    assert storage.get_debug_mode(999) is False


# ---------------------------------------------------------------------------
# Test 4 — Aislamiento: usuario A con debug on no afecta a usuario B
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_debug_isolation_between_users():
    from handlers.text_handler import handle_text

    update_a = make_update(user_id=201)
    update_b = make_update(user_id=202)
    ctx_a = make_context()
    ctx_b = make_context()

    def mock_get_debug(tid):
        return tid == 201  # solo A tiene debug on

    with patch("handlers.text_handler.process_message", return_value=BASE_RESULT), \
         patch("handlers._flow.get_debug_mode", side_effect=mock_get_debug):
        await handle_text(update_a, ctx_a)
        await handle_text(update_b, ctx_b)

    text_a = update_a.message.reply_text.call_args[0][0]
    text_b = update_b.message.reply_text.call_args[0][0]

    assert "🔍" in text_a
    assert "🔍" not in text_b
