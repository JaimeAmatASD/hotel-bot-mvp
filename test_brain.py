"""Tests de integración — requieren red y API keys reales. Correr con: pytest -m integration"""
import pytest
from pathlib import Path
from brain import process_message
from audio_test_cases import AUDIO_TEST_CASES

AUDIOS_DIR = Path(__file__).parent / "audios"
MARIA = {"nombre": "María", "departamento": "HOUSEKEEPING", "idioma": "es"}
ANDREI = {"nombre": "Andrei", "departamento": "MANTENIMIENTO", "idioma": "ro"}


@pytest.mark.integration
def test_texto_espanol():
    result = process_message("Hay un goteo en el aire acondicionado de la 204", MARIA)
    meta = result.get("_meta", {})
    assert result.get("tipo") == "INCIDENCIA"
    assert meta.get("input_type") == "text"
    assert meta.get("transcription") is None
    assert meta.get("error") is None


@pytest.mark.integration
def test_audio_espanol():
    audio_es = AUDIOS_DIR / AUDIO_TEST_CASES[0]["filename"]
    if not audio_es.exists():
        pytest.skip(f"Audio no encontrado: {AUDIO_TEST_CASES[0]['filename']}")
    result = process_message(str(audio_es), MARIA, is_audio=True)
    meta = result.get("_meta", {})
    assert result.get("tipo") != "ERROR"
    assert meta.get("input_type") == "audio"
    assert meta.get("transcription") is not None
    assert meta.get("audio_language_detected") == "Spanish"


@pytest.mark.integration
def test_audio_rumano():
    audio_ro = AUDIOS_DIR / AUDIO_TEST_CASES[4]["filename"]
    if not audio_ro.exists():
        pytest.skip(f"Audio no encontrado: {AUDIO_TEST_CASES[4]['filename']}")
    result = process_message(str(audio_ro), ANDREI, is_audio=True, language_hint="ro")
    meta = result.get("_meta", {})
    assert result.get("tipo") != "ERROR"
    assert meta.get("audio_language_detected") == "Romanian"
    assert result.get("descripcion") is not None


@pytest.mark.integration
def test_audio_inexistente():
    result = process_message("audios/no_existe.flac", MARIA, is_audio=True)
    meta = result.get("_meta", {})
    assert result.get("tipo") == "ERROR"
    assert meta.get("error") is not None
    assert meta.get("input_type") == "audio"


@pytest.mark.integration
def test_texto_vacio():
    result = process_message("", MARIA)
    meta = result.get("_meta", {})
    assert result.get("tipo") in ("ERROR", "NO_REPORTE")
    assert meta.get("input_type") == "text"
