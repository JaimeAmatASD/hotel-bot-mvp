"""Health-check de las APIs externas. Se corre una vez al arrancar el bot.

El objetivo es enterarte vos de que una credencial caducó, y no que lo descubra un
empleado cuando el bot le conteste ERROR a una nota de voz.

Usa llamadas baratas de solo-lectura (listar modelos, getMe, abrir la hoja): validan
la credencial sin consumir cuota de generación ni de transcripción.

NUNCA levanta excepción ni frena el arranque: una API caída degrada el bot, no lo tumba.
"""
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Peor caso tolerado para el chequeo completo; los 4 corren en paralelo.
TIMEOUT_SEGUNDOS = 20.0

_MAX_DETALLE = 160


@dataclass(frozen=True)
class ApiStatus:
    nombre: str
    ok: bool
    detalle: str
    impacto: str


def _redact(texto: str) -> str:
    """Saca del texto cualquier secreto del entorno antes de que llegue al log.

    Las excepciones de httpx incluyen la URL completa, y la URL de la Bot API lleva
    el token adentro. Sin esto, un fallo de Telegram escribiría el token en el log.
    """
    limpio = str(texto)
    for var in ("TELEGRAM_BOT_TOKEN", "GROQ_API_KEY", "GEMINI_API_KEY"):
        secreto = os.environ.get(var)
        if secreto and secreto in limpio:
            limpio = limpio.replace(secreto, f"<{var}>")
    return limpio[:_MAX_DETALLE]


def _check_telegram() -> ApiStatus:
    impacto = "el bot no puede recibir ni responder mensajes"
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return ApiStatus("Telegram", False, "TELEGRAM_BOT_TOKEN no configurada", impacto)

    import httpx
    try:
        response = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        if response.status_code != 200:
            return ApiStatus("Telegram", False,
                             f"HTTP {response.status_code} — token revocado o inválido", impacto)
        nombre = response.json().get("result", {}).get("username", "?")
        return ApiStatus("Telegram", True, f"@{nombre}", impacto)
    except Exception as e:
        return ApiStatus("Telegram", False, _redact(f"{type(e).__name__}: {e}"), impacto)


def _check_gemini() -> ApiStatus:
    impacto = "no se pueden clasificar mensajes — todo reporte va a fallar"
    if not os.environ.get("GEMINI_API_KEY"):
        return ApiStatus("Gemini", False, "GEMINI_API_KEY no configurada", impacto)

    import classifier
    try:
        next(iter(classifier._get_client().models.list()))
        return ApiStatus("Gemini", True, "key válida", impacto)
    except Exception as e:
        return ApiStatus("Gemini", False, _redact(f"{type(e).__name__}: {e}"), impacto)


def _check_groq() -> ApiStatus:
    impacto = "las notas de voz van a fallar (el texto sigue funcionando)"
    if not os.environ.get("GROQ_API_KEY"):
        return ApiStatus("Groq", False, "GROQ_API_KEY no configurada", impacto)

    import transcriber
    try:
        transcriber._get_client().models.list()
        return ApiStatus("Groq", True, "key válida", impacto)
    except Exception as e:
        return ApiStatus("Groq", False, _redact(f"{type(e).__name__}: {e}"), impacto)


def _check_sheets() -> ApiStatus:
    impacto = "el espejo de Sheets queda desactualizado (SQLite sigue siendo la fuente de verdad)"
    if not os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or not os.environ.get("SHEET_ID"):
        return ApiStatus("Sheets", False, "GOOGLE_SERVICE_ACCOUNT_JSON o SHEET_ID no configuradas", impacto)

    import sheets_sync
    try:
        worksheet = sheets_sync._get_worksheet("Incidencias")
        return ApiStatus("Sheets", True, worksheet.spreadsheet.title, impacto)
    except Exception as e:
        return ApiStatus("Sheets", False, _redact(f"{type(e).__name__}: {e}"), impacto)


_CHECKS = (_check_telegram, _check_gemini, _check_groq, _check_sheets)


def check_apis(timeout: float = TIMEOUT_SEGUNDOS) -> list[ApiStatus]:
    """Corre los 4 chequeos en paralelo. Nunca levanta: lo que falla vuelve como ok=False."""
    pool = ThreadPoolExecutor(max_workers=len(_CHECKS))
    futures = {pool.submit(check): check for check in _CHECKS}
    resultados: dict = {}

    try:
        for future in as_completed(futures, timeout=timeout):
            check = futures[future]
            nombre = check.__name__.removeprefix("_check_").capitalize()
            try:
                resultados[check] = future.result()
            except Exception as e:
                # Un check sólo llega acá si rompió fuera de su propio try (p. ej. un
                # import roto). Ni así puede impedir que el bot arranque.
                resultados[check] = ApiStatus(
                    nombre, False, _redact(f"{type(e).__name__}: {e}"), "desconocido")
    except TimeoutError:
        pass  # los que faltan se reportan abajo como sin respuesta
    finally:
        # wait=False: un check colgado no puede demorar el arranque del bot.
        pool.shutdown(wait=False, cancel_futures=True)

    return [
        resultados.get(
            check,
            ApiStatus(check.__name__.removeprefix("_check_").capitalize(), False,
                      f"sin respuesta en {timeout:.0f}s", "desconocido"),
        )
        for check in _CHECKS
    ]


def log_api_health(timeout: float = TIMEOUT_SEGUNDOS) -> list[ApiStatus]:
    """Chequea y deja el resultado en el log. Devuelve los estados por si el caller los quiere."""
    estados = check_apis(timeout)
    caidas = [e for e in estados if not e.ok]

    if not caidas:
        logger.info("health: %d/%d APIs OK", len(estados), len(estados))
        return estados

    logger.warning("health: %d de %d APIs NO responden", len(caidas), len(estados))
    for estado in caidas:
        logger.warning("health: %s CAÍDA — %s | impacto: %s",
                       estado.nombre, estado.detalle, estado.impacto)
    return estados
