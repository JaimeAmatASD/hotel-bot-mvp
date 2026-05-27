"""Display ID generation for user-facing references like INC-N, REP-N, etc."""
from config.enums import ReportType

_DISPLAY_PREFIXES = {
    ReportType.INCIDENCIA: "INC",
    ReportType.OBSERVACION: "OBS",
    ReportType.GUEST_INTEL: "MEM",
    ReportType.NO_REPORTE: "NR",
    ReportType.REPORT: "REP",
}


def generate_display_id(tipo: str, id: int) -> str:
    prefix = _DISPLAY_PREFIXES.get(tipo, "??")
    return f"{prefix}-{id:03d}"
