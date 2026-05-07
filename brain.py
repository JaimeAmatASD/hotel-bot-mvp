from classifier import classify
from transcriber import transcribe


def process_message(
    input: str,
    employee: dict,
    *,
    is_audio: bool = False,
    language_hint: str | None = None,
) -> dict:
    if is_audio:
        t = transcribe(input, language=language_hint)

        if t["error"] or not t["text"]:
            return {
                "tipo": "ERROR",
                "ubicacion": None,
                "categoria": None,
                "subcategoria": None,
                "prioridad": None,
                "descripcion": t["error"] or "transcripción vacía",
                "idioma_original": None,
                "huesped_afectado": None,
                "habitacion_huesped": None,
                "tipo_nota_huesped": None,
                "campos_faltantes": [],
                "confianza": 0,
                "_meta": {
                    "input_type": "audio",
                    "transcription": t["text"] or None,
                    "audio_language_detected": t["language"],
                    "audio_duration_seconds": t["duration_seconds"],
                    "error": t["error"] or "transcripción vacía",
                },
            }

        result = classify(t["text"], employee)
        result["_meta"] = {
            "input_type": "audio",
            "transcription": t["text"],
            "audio_language_detected": t["language"],
            "audio_duration_seconds": t["duration_seconds"],
            "error": None,
        }
        return result

    if not input.strip():
        return {
            "tipo": "ERROR",
            "ubicacion": None,
            "categoria": None,
            "subcategoria": None,
            "prioridad": None,
            "descripcion": "mensaje vacío",
            "idioma_original": None,
            "huesped_afectado": None,
            "habitacion_huesped": None,
            "tipo_nota_huesped": None,
            "campos_faltantes": [],
            "confianza": 0,
            "_meta": {
                "input_type": "text",
                "transcription": None,
                "audio_language_detected": None,
                "audio_duration_seconds": None,
                "error": "mensaje vacío",
            },
        }

    result = classify(input, employee)
    result["_meta"] = {
        "input_type": "text",
        "transcription": None,
        "audio_language_detected": None,
        "audio_duration_seconds": None,
        "error": None,
    }
    return result
