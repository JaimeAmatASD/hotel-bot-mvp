import os
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY no encontrada en .env")
        _client = Groq(api_key=api_key)
    return _client


def transcribe(audio_path: str, language: str | None = None) -> dict:
    path = Path(audio_path)

    if not path.exists():
        return {"text": "", "language": None, "duration_seconds": 0,
                "error": f"Archivo no encontrado: {audio_path}"}

    try:
        with open(path, "rb") as f:
            params = {
                "file": (path.name, f),
                "model": "whisper-large-v3-turbo",
                "response_format": "verbose_json",
            }
            if language:
                params["language"] = language

            response = _get_client().audio.transcriptions.create(**params)

        text = response.text.strip()

        if not text:
            return {"text": "", "language": getattr(response, "language", None),
                    "duration_seconds": getattr(response, "duration", 0),
                    "error": "audio vacío o sin habla detectada"}

        return {
            "text": text,
            "language": getattr(response, "language", language),
            "duration_seconds": getattr(response, "duration", 0),
            "error": None,
        }

    except Exception as e:
        return {"text": "", "language": None, "duration_seconds": 0, "error": str(e)}
