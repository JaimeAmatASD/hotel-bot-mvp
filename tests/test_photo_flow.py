"""Tests for photo handler flow (Sprint A.3)."""
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

EMPLOYEE = {"nombre": "Ana García", "departamento": "HOUSEKEEPING", "idioma": "es"}

# process_message is fully mocked so the file only needs to exist, not be a real JPEG
FAKE_IMAGE_BYTES = b"FAKE_IMAGE_DATA"


def _result(tipo="INCIDENCIA", categoria="MANTENIMIENTO", confianza=0.9,
            needs_followup=None, **kwargs):
    r = {
        "tipo": tipo, "ubicacion": "Lobby", "categoria": categoria,
        "subcategoria": None, "prioridad": "MEDIA", "descripcion": "Goteo en grifo",
        "idioma_original": "es", "huesped_afectado": False, "habitacion_huesped": None,
        "tipo_nota_huesped": None, "campos_faltantes": [], "confianza": confianza,
        "_meta": {"input_type": "photo", "transcription": None,
                   "audio_language_detected": None, "audio_duration_seconds": None,
                   "error": None, "photo_path": "data/photos/42/fake.jpg"},
        **kwargs,
    }
    if needs_followup:
        r["needs_followup"] = needs_followup
    return r


def make_update(caption=None, user_id=42):
    update = MagicMock()
    update.message = AsyncMock()
    update.message.caption = caption
    update.message.text = None
    update.message.voice = None
    update.message.audio = None
    # Simulate photo list with one entry
    photo_mock = MagicMock()
    photo_mock.file_id = "FAKE_FILE_ID_12345"
    update.message.photo = [photo_mock]
    update.effective_user = MagicMock(id=user_id)
    return update


def make_context():
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.bot = AsyncMock()
    return ctx


def _patch_photo_download(tmp_path):
    """Returns a file mock whose download_to_drive writes fake bytes to disk."""
    async def fake_download(path):
        Path(path).write_bytes(FAKE_IMAGE_BYTES)

    file_mock = AsyncMock()
    file_mock.download_to_drive = fake_download
    return file_mock


# ---------------------------------------------------------------------------
# Test 1 — Foto sola clasifica como INCIDENCIA/MANTENIMIENTO
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_photo_alone_classifies(tmp_path, monkeypatch):
    from handlers.photo_handler import handle_photo
    monkeypatch.chdir(tmp_path)

    result = _result(tipo="INCIDENCIA", categoria="MANTENIMIENTO")
    update = make_update(caption=None)
    ctx = make_context()
    ctx.bot.get_file = AsyncMock(return_value=_patch_photo_download(tmp_path))

    with patch("handlers.photo_handler.process_message", return_value=result), \
         patch("handlers._flow.get_debug_mode", return_value=False):
        await handle_photo(update, ctx)

    assert ctx.user_data["pending"]["result"]["tipo"] == "INCIDENCIA"
    assert ctx.user_data["pending"]["result"]["categoria"] == "MANTENIMIENTO"
    assert "image_path" in ctx.user_data["pending"]


# ---------------------------------------------------------------------------
# Test 2 — Foto + caption: process_message recibe imagen + texto
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_photo_with_caption(tmp_path, monkeypatch):
    from handlers.photo_handler import handle_photo
    monkeypatch.chdir(tmp_path)

    result = _result(descripcion="Grifo roto desde ayer, habitación 305")
    update = make_update(caption="está roto desde ayer")
    ctx = make_context()
    ctx.bot.get_file = AsyncMock(return_value=_patch_photo_download(tmp_path))

    with patch("handlers.photo_handler.process_message", return_value=result) as mock_pm, \
         patch("handlers._flow.get_debug_mode", return_value=False):
        await handle_photo(update, ctx)

    call_kwargs = mock_pm.call_args
    assert call_kwargs[0][0] == "está roto desde ayer"  # caption passed as input
    assert call_kwargs[1]["image_path"] is not None     # image_path provided


# ---------------------------------------------------------------------------
# Test 3 — Caption GUEST_INTEL gana sobre imagen
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_caption_wins_over_image(tmp_path, monkeypatch):
    from handlers.photo_handler import handle_photo
    monkeypatch.chdir(tmp_path)

    guest_result = _result(
        tipo="GUEST_INTEL", categoria=None,
        descripcion="Alergia a frutos secos, habitación 215",
        tipo_nota_huesped="ALERGIA",
    )
    update = make_update(caption="alergia del huésped a frutos secos en hab 215")
    ctx = make_context()
    ctx.bot.get_file = AsyncMock(return_value=_patch_photo_download(tmp_path))

    with patch("handlers.photo_handler.process_message", return_value=guest_result), \
         patch("handlers._flow.get_debug_mode", return_value=False):
        await handle_photo(update, ctx)

    assert ctx.user_data["pending"]["result"]["tipo"] == "GUEST_INTEL"
    assert ctx.user_data["pending"]["result"]["tipo_nota_huesped"] == "ALERGIA"


# ---------------------------------------------------------------------------
# Test 4 — Foto ambigua (confianza baja) pide reformular
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ambiguous_photo_asks_reformulate(tmp_path, monkeypatch):
    from handlers.photo_handler import handle_photo
    monkeypatch.chdir(tmp_path)

    low_conf = _result(confianza=0.4)
    update = make_update(caption=None)
    ctx = make_context()
    ctx.bot.get_file = AsyncMock(return_value=_patch_photo_download(tmp_path))

    with patch("handlers.photo_handler.process_message", return_value=low_conf), \
         patch("handlers._flow.get_debug_mode", return_value=False):
        await handle_photo(update, ctx)

    assert "pending" not in ctx.user_data
    # Bot sent "📸 Procesando foto..." + reformulate message
    assert update.message.reply_text.call_count == 2
    last_msg = update.message.reply_text.call_args_list[-1][0][0]
    assert "entendí" in last_msg.lower() or "contarme" in last_msg.lower()


# ---------------------------------------------------------------------------
# Test 5 — Foto + corrección: previous_context incluye image_path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_photo_correction_preserves_image(tmp_path, monkeypatch):
    from handlers.text_handler import handle_text
    monkeypatch.chdir(tmp_path)

    original_result = _result()
    corrected_result = _result(descripcion="Grifo roto, habitación 412", ubicacion="Habitación 412")

    user_data = {
        "pending": {
            "result": original_result,
            "original_text": "",
            "image_path": "data/photos/42/original.jpg",
        },
        "awaiting_correction": True,
        "correction_started_at": datetime.now().isoformat(),
    }
    update = MagicMock()
    update.message = AsyncMock()
    update.message.text = "es en la 412"
    update.message.voice = None
    update.message.audio = None
    update.effective_user = MagicMock(id=42)

    ctx = MagicMock()
    ctx.user_data = user_data
    ctx.bot = AsyncMock()

    with patch("handlers.text_handler.process_message", return_value=corrected_result) as mock_pm, \
         patch("handlers._flow.get_debug_mode", return_value=False):
        await handle_text(update, ctx)

    call_kwargs = mock_pm.call_args.kwargs
    assert call_kwargs["previous_context"]["image_path"] == "data/photos/42/original.jpg"
