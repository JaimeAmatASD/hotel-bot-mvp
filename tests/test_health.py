"""Tests del health-check de APIs. Sin red: todo mockeado."""
import logging
import time
from unittest.mock import patch

import pytest

import health
from health import ApiStatus


# --- Redacción de secretos -------------------------------------------------
# La URL de la Bot API lleva el token adentro y httpx la mete en sus excepciones.
# Si esto se rompe, el token termina escrito en el log.

def test_redact_saca_el_token_de_telegram(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:SECRETO")
    error = "Client error for url https://api.telegram.org/bot123:SECRETO/getMe"

    limpio = health._redact(error)

    assert "SECRETO" not in limpio
    assert "<TELEGRAM_BOT_TOKEN>" in limpio


def test_redact_saca_las_keys_de_groq_y_gemini(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_secreta")
    monkeypatch.setenv("GEMINI_API_KEY", "AIza_secreta")

    limpio = health._redact("falló con gsk_secreta y AIza_secreta")

    assert "gsk_secreta" not in limpio
    assert "AIza_secreta" not in limpio


def test_redact_trunca_mensajes_largos():
    assert len(health._redact("x" * 500)) == health._MAX_DETALLE


# --- Credenciales ausentes -------------------------------------------------

def test_credencial_ausente_reporta_caida(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    estado = health._check_groq()

    assert estado.ok is False
    assert "GROQ_API_KEY" in estado.detalle


def test_sheets_requiere_ambas_variables(monkeypatch):
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", "/tmp/cred.json")
    monkeypatch.delenv("SHEET_ID", raising=False)

    assert health._check_sheets().ok is False


# --- check_apis nunca rompe el arranque ------------------------------------

def test_check_apis_devuelve_las_cuatro():
    with patch.object(health, "_CHECKS", (health._check_groq,)):
        assert len(health.check_apis()) == 1

    assert len(health.check_apis(timeout=0.01)) == 4


def test_un_check_que_explota_no_propaga():
    def check_roto():
        raise RuntimeError("boom")

    with patch.object(health, "_CHECKS", (check_roto,)):
        estados = health.check_apis(timeout=2)

    assert len(estados) == 1
    assert estados[0].ok is False


def test_check_colgado_no_frena_el_arranque():
    def check_lento():
        time.sleep(30)

    with patch.object(health, "_CHECKS", (check_lento,)):
        inicio = time.monotonic()
        estados = health.check_apis(timeout=0.2)
        transcurrido = time.monotonic() - inicio

    assert transcurrido < 5, "el chequeo debe rendirse, no esperar al check colgado"
    assert estados[0].ok is False
    assert "sin respuesta" in estados[0].detalle


# --- Logging ---------------------------------------------------------------

def test_todo_ok_loguea_info(caplog):
    ok = [ApiStatus("Groq", True, "key válida", "impacto")]
    with patch.object(health, "check_apis", return_value=ok):
        with caplog.at_level(logging.INFO, logger="health"):
            health.log_api_health()

    assert "1/1 APIs OK" in caplog.text
    assert "WARNING" not in caplog.text


def test_api_caida_loguea_warning_con_impacto(caplog):
    caidos = [
        ApiStatus("Groq", False, "401 expired_api_key", "las notas de voz van a fallar"),
        ApiStatus("Gemini", True, "key válida", "impacto"),
    ]
    with patch.object(health, "check_apis", return_value=caidos):
        with caplog.at_level(logging.WARNING, logger="health"):
            estados = health.log_api_health()

    assert "Groq CAÍDA" in caplog.text
    assert "expired_api_key" in caplog.text
    assert "las notas de voz van a fallar" in caplog.text
    assert "Gemini" not in caplog.text, "no se loguean las APIs que están sanas"
    assert estados == caidos
