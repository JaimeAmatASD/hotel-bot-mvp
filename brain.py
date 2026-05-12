from classifier import classify
from transcriber import transcribe
from config.rules import get_critical_field, is_location_complete, MISSING_FIELD_QUESTIONS


def _apply_followup(result: dict) -> dict:
    """Mutates result in-place: detects generic location and adds needs_followup if needed."""
    tipo = result.get("tipo")
    if tipo in ("ERROR", "NO_REPORTE"):
        return result

    campos = result.get("campos_faltantes") or []

    # If location is absent or incomplete (no room number, no common area), mark as missing
    if tipo == "INCIDENCIA" and not is_location_complete(result.get("ubicacion")):
        normalized = [c.lower() for c in campos]
        if "ubicacion" not in normalized and "ubicación" not in normalized:
            campos = list(campos) + ["ubicacion"]
            result["campos_faltantes"] = campos

    critical = get_critical_field(tipo, campos)
    if critical:
        question = MISSING_FIELD_QUESTIONS.get(
            critical.lower().replace("ó", "o").replace("á", "a"),
            f"Necesito un dato más: ¿{critical}?"
        )
        result["needs_followup"] = {"field": critical, "question": question}

    return result


def process_message(
    input: str,
    employee: dict,
    *,
    is_audio: bool = False,
    language_hint: str | None = None,
    previous_context: dict | None = None,
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

        result = classify(t["text"], employee, previous_context=previous_context)
        result["_meta"] = {
            "input_type": "audio",
            "transcription": t["text"],
            "audio_language_detected": t["language"],
            "audio_duration_seconds": t["duration_seconds"],
            "error": None,
        }
        return _apply_followup(result)

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

    result = classify(input, employee, previous_context=previous_context)
    result["_meta"] = {
        "input_type": "text",
        "transcription": None,
        "audio_language_detected": None,
        "audio_duration_seconds": None,
        "error": None,
    }
    return _apply_followup(result)
