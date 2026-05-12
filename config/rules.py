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
    """Returns canonical critical field name if any campos_faltantes matches, else None.
    Uses substring matching so 'número de habitación' matches 'habitacion'."""
    critical = CRITICAL_MISSING_FIELDS.get(tipo, [])
    critical_normalized = [_normalize(c) for c in critical]
    for campo in campos_faltantes:
        campo_norm = _normalize(campo)
        for i, crit_norm in enumerate(critical_normalized):
            if crit_norm in campo_norm or campo_norm in crit_norm:
                return critical[i]  # return canonical form for MISSING_FIELD_QUESTIONS lookup
    return None


def is_generic_location(ubicacion: str | None) -> bool:
    if not ubicacion:
        return False
    if re.search(r"\d", ubicacion):
        return False
    return bool(_GENERIC_LOCATION_WORDS.match(ubicacion.strip()))
