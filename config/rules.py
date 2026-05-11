import re
import unicodedata

CORRECTION_TIMEOUT_MINUTES = 5

CRITICAL_MISSING_FIELDS = {
    "INCIDENCIA": ["habitación", "ubicación", "habitacion", "ubicacion"],
    "GUEST_INTEL": ["habitación", "habitacion"],
    "OBSERVACION": [],
    "NO_REPORTE": [],
}

MISSING_FIELD_QUESTIONS = {
    "habitación": "¿En qué habitación?",
    "habitacion": "¿En qué habitación?",
    "ubicación": "¿Dónde exactamente?",
    "ubicacion": "¿Dónde exactamente?",
}

_GENERIC_LOCATION_WORDS = re.compile(
    r"^(una?\s+)?(habitaci[oó]n|ba[ñn]o|cuarto|zona|[aá]rea|pasillo|lobby|recepci[oó]n|piscina|jard[ií]n)(\s+en\b.*)?$",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode().lower().strip()


def get_critical_field(tipo: str, campos_faltantes: list) -> str | None:
    critical = CRITICAL_MISSING_FIELDS.get(tipo, [])
    critical_normalized = [_normalize(c) for c in critical]
    for campo in campos_faltantes:
        if _normalize(campo) in critical_normalized:
            return campo
    return None


def is_generic_location(ubicacion: str | None) -> bool:
    if not ubicacion:
        return False
    if re.search(r"\d", ubicacion):
        return False
    return bool(_GENERIC_LOCATION_WORDS.match(ubicacion.strip()))
