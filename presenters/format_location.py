"""Location label helpers."""
import re

_ROOM_RE = re.compile(r"\bhabitaci[oó]n\s+(?=\d)", re.IGNORECASE)


def shorten_room_label(ubicacion: str | None) -> str:
    """'Habitación 204, baño' -> 'Hab 204, baño'. Solo acorta si sigue un número."""
    if not ubicacion:
        return ""
    return _ROOM_RE.sub("Hab ", ubicacion)
