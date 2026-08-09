"""Health-check de las 4 APIs externas — requieren red y credenciales reales.
Correr con: venv/bin/pytest -m integration -o addopts=''

No envía mensajes ni escribe en Sheets: todo es read-only. No hace falta un teléfono
ni un chat de Telegram para correrlos.

Si una credencial no está configurada → skip. Si está configurada pero no funciona → fail
con el motivo, para saber de un vistazo qué key hay que renovar.
"""
import os
from pathlib import Path

import httpx
import pytest

import classifier
import sheets_sync
import transcriber

AUDIOS_DIR = Path(__file__).parent.parent.parent / "audios"
EMPLEADO = {"nombre": "María", "departamento": "HOUSEKEEPING", "idioma": "es"}


@pytest.mark.integration
def test_telegram_bot_api_responde():
    """El token del bot sigue vivo. `getMe` es read-only: no manda ningún mensaje."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        pytest.skip("TELEGRAM_BOT_TOKEN no configurada en .env")

    response = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=15)

    assert response.status_code == 200, (
        f"Telegram Bot API rechazó el token (HTTP {response.status_code}): {response.text}. "
        "Revisar TELEGRAM_BOT_TOKEN en .env — probablemente revocado desde @BotFather."
    )
    result = response.json().get("result", {})
    assert result.get("is_bot") is True, f"Respuesta inesperada de getMe: {response.json()}"


@pytest.mark.integration
def test_gemini_clasifica():
    """La API de Gemini responde y devuelve un JSON con la forma esperada."""
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY no configurada en .env")

    result = classifier.classify("Hay un goteo en el aire acondicionado de la 204", EMPLEADO)

    assert result.get("tipo") == "INCIDENCIA", (
        f"Gemini no clasificó el mensaje como esperado: {result}. "
        "Si el tipo es ERROR, revisar GEMINI_API_KEY y la cuota del proyecto GCP."
    )


@pytest.mark.integration
def test_groq_transcribe_audio():
    """Whisper en Groq transcribe un audio real. Cubre la ruta de notas de voz del bot."""
    if not os.environ.get("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY no configurada en .env")

    audio = AUDIOS_DIR / "es_incidencia_204.flac"
    if not audio.exists():
        pytest.skip(f"Audio de fixture no encontrado: {audio}")

    result = transcriber.transcribe(str(audio), language="es")

    assert result["error"] is None, (
        f"Groq falló al transcribir: {result['error']}. "
        "Si dice 'expired_api_key', renovar GROQ_API_KEY en console.groq.com."
    )
    assert result["text"], "Groq devolvió una transcripción vacía"


@pytest.mark.integration
def test_sheets_accesible():
    """El service account puede abrir el spreadsheet y ve las 4 pestañas con sus headers.
    Solo lee: no escribe filas ni toca los headers existentes."""
    if not os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or not os.environ.get("SHEET_ID"):
        pytest.skip("GOOGLE_SERVICE_ACCOUNT_JSON o SHEET_ID no configuradas en .env")

    for nombre, headers_esperados in sheets_sync._HEADERS.items():
        try:
            worksheet = sheets_sync._get_worksheet(nombre)
        except Exception as e:
            pytest.fail(
                f"No se pudo abrir la pestaña '{nombre}': {type(e).__name__}: {e}. "
                "Revisar que el service account siga compartido en el Sheet y que la "
                "Google Sheets API siga habilitada en el proyecto GCP."
            )

        headers_reales = worksheet.row_values(1)
        assert headers_reales == headers_esperados, (
            f"Los headers de '{nombre}' no coinciden con los esperados.\n"
            f"  esperados: {headers_esperados}\n"
            f"  en Sheets: {headers_reales}"
        )
