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

COMMON_AREAS = {
    "lobby", "recepcion", "spa", "piscina", "pool", "cocina", "comedor",
    "restaurante", "bar", "jardin", "terraza", "patio", "parking", "garaje",
    "gimnasio", "gym", "ascensor", "escalera", "pasillo", "lavanderia",
    "almacen", "oficina", "sauna", "jacuzzi",
}


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode().lower().strip()


def is_location_complete(ubicacion: str | None) -> bool:
    """Returns True if the location is specific enough (has a room number or a known common area)."""
    if not ubicacion:
        return False
    norm = _normalize(ubicacion)
    if any(c.isdigit() for c in norm):
        return True
    for word in re.split(r"[\s,;.]+", norm):
        if word in COMMON_AREAS:
            return True
    return False


def get_critical_field(tipo: str, campos_faltantes: list) -> str | None:
    """Returns canonical critical field name if any campos_faltantes matches, else None.
    Uses substring matching so 'número de habitación' matches 'habitacion'."""
    critical = CRITICAL_MISSING_FIELDS.get(tipo, [])
    critical_normalized = [_normalize(c) for c in critical]
    for campo in campos_faltantes:
        campo_norm = _normalize(campo)
        for i, crit_norm in enumerate(critical_normalized):
            if crit_norm in campo_norm or campo_norm in crit_norm:
                return critical[i]
    return None
