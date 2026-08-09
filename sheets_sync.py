"""Capa de visibilidad Google Sheets. SQLite es la única fuente de verdad.
Si Sheets falla, se loguea pero nunca se propaga — el bot no se cae."""

import asyncio
import logging
import os
import re
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

import report_processor
from config.enums import IncidentState, ReportType

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_client: gspread.Client | None = None
_spreadsheet: gspread.Spreadsheet | None = None
_worksheets: dict[str, gspread.Worksheet] = {}

_HEADERS = {
    "Incidencias":       ["ID", "Fecha/hora creación", "Empleado", "Departamento",
                          "Ubicación", "Categoría", "Subcategoría", "Prioridad",
                          "Descripción", "Estado", "Asignado a", "Última actualización",
                          "Foto", "Asignado por", "Resuelto por", "Validado por"],
    "Guest Intel":       ["ID", "Fecha/hora", "Empleado", "Habitación huésped",
                          "Tipo de nota", "Descripción", "Idioma original"],
    "Observaciones":     ["ID", "Fecha/hora", "Empleado", "Departamento",
                          "Descripción", "Categoría"],
    "Reportes de turno": ["ID", "Fecha/hora de cierre", "Empleado",
                          "Cantidad de ítems", "Desglose", "Resumen / link"],
}

_ROOM_LOCATION_RE = re.compile(
    r"\b(?:hab(?:itaci[oó]n)?\.?|room|cuarto)\s*[-#:]?\s*(\d+[A-Za-z]?)\b",
    re.IGNORECASE,
)


def _format_room_for_sheet(value: str | None) -> str:
    """Return a filter-friendly room value for Sheets: 'Habitación 48' -> '48'."""
    text = (value or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"\d+[A-Za-z]?", text):
        return text
    match = _ROOM_LOCATION_RE.search(text)
    if match:
        return match.group(1)
    return text


def _get_client() -> gspread.Client:
    global _client
    if _client is None:
        json_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not json_path:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON no encontrada en .env")
        creds = Credentials.from_service_account_file(json_path, scopes=_SCOPES)
        _client = gspread.authorize(creds)
    return _client


def _get_worksheet(name: str) -> gspread.Worksheet:
    global _spreadsheet
    if name not in _worksheets:
        if _spreadsheet is None:
            sheet_id = os.environ.get("SHEET_ID")
            if not sheet_id:
                raise RuntimeError("SHEET_ID no encontrada en .env")
            _spreadsheet = _get_client().open_by_key(sheet_id)
        _worksheets[name] = _spreadsheet.worksheet(name)
    return _worksheets[name]


def ensure_headers() -> None:
    """Verifica/crea encabezados en cada hoja. Idempotente. Llamar al startup del bot."""
    try:
        for sheet_name, headers in _HEADERS.items():
            ws = _get_worksheet(sheet_name)
            row1 = ws.row_values(1)
            if not row1 or row1[0] != headers[0]:
                ws.insert_row(headers, 1)
                logger.info(f"sheets_sync: encabezados escritos en '{sheet_name}'")
    except Exception as e:
        logger.error(f"sheets_sync: error en ensure_headers: {e}")


# ---------------------------------------------------------------------------
# Sync interno (síncrono, se llama desde asyncio.to_thread)
# ---------------------------------------------------------------------------

def _sync_incidencia_sync(incident: dict, display_id: str, employees: dict | None) -> None:
    ws = _get_worksheet("Incidencias")

    assignee_name = incident.get("_assignee_name", "")
    if not assignee_name and incident.get("assigned_to_telegram_id") and employees:
        emp = employees.get(int(incident["assigned_to_telegram_id"]))
        if emp:
            assignee_name = emp.get("nombre", "")

    def _name(tid):
        if not tid or not employees:
            return ""
        e = employees.get(int(tid))
        return e.get("nombre", "") if e else ""

    row = [
        display_id,
        incident.get("timestamp", ""),
        incident.get("employee_name", ""),
        incident.get("employee_dept", ""),
        _format_room_for_sheet(incident.get("ubicacion")),
        incident.get("categoria", "") or "",
        incident.get("subcategoria", "") or "",
        incident.get("prioridad", "") or "",
        incident.get("descripcion", "") or "",
        incident.get("estado", IncidentState.NUEVA),
        assignee_name,
        datetime.now().isoformat(timespec="seconds"),
        "Sí" if incident.get("photo_path") else "No",
        _name(incident.get("assigned_by")),
        _name(incident.get("resolved_by")),
        _name(incident.get("closed_by")),
    ]

    col_a = ws.col_values(1)
    if display_id in col_a:
        row_num = col_a.index(display_id) + 1
        ws.update(f"A{row_num}:P{row_num}", [row])
    else:
        ws.append_row(row)


def _sync_guest_intel_sync(result: dict, employee: dict, display_id: str) -> None:
    ws = _get_worksheet("Guest Intel")
    row = [
        display_id,
        datetime.now().isoformat(timespec="seconds"),
        employee.get("nombre", ""),
        _format_room_for_sheet(result.get("habitacion_huesped")),
        result.get("tipo_nota_huesped", "") or "",
        result.get("descripcion", "") or "",
        result.get("idioma_original", "") or "",
    ]
    ws.append_row(row)


def _sync_observacion_sync(result: dict, employee: dict, display_id: str) -> None:
    ws = _get_worksheet("Observaciones")
    row = [
        display_id,
        datetime.now().isoformat(timespec="seconds"),
        employee.get("nombre", ""),
        employee.get("departamento", ""),
        result.get("descripcion", "") or "",
        result.get("categoria", "") or "",
    ]
    ws.append_row(row)


def _sync_reporte_sync(report: dict, items: list[dict], display_id: str) -> None:
    ws = _get_worksheet("Reportes de turno")
    n_inc = sum(1 for i in items if i.get("tipo") == ReportType.INCIDENCIA)
    n_gi  = sum(1 for i in items if i.get("tipo") == ReportType.GUEST_INTEL)
    n_obs = sum(1 for i in items if i.get("tipo") == ReportType.OBSERVACION)
    desglose_parts = []
    if n_inc: desglose_parts.append(f"{n_inc} INC")
    if n_gi:  desglose_parts.append(f"{n_gi} GI")
    if n_obs: desglose_parts.append(f"{n_obs} OBS")
    desglose = ", ".join(desglose_parts) or f"{len(items)} ítems"
    row = [
        display_id,
        report.get("closed_at") or report.get("started_at", ""),
        report.get("employee_name", ""),
        len(items),
        desglose,
        report_processor.format_report_for_sheet(items),
    ]
    ws.append_row(row)


# ---------------------------------------------------------------------------
# API pública async
# ---------------------------------------------------------------------------

async def sync_incidencia(incident: dict, display_id: str, employees: dict | None = None) -> bool:
    try:
        await asyncio.to_thread(_sync_incidencia_sync, incident, display_id, employees)
        return True
    except Exception as e:
        logger.error(f"sheets_sync: sync_incidencia falló ({display_id}): {e}")
        return False


async def sync_guest_intel(result: dict, employee: dict, display_id: str) -> bool:
    try:
        await asyncio.to_thread(_sync_guest_intel_sync, result, employee, display_id)
        return True
    except Exception as e:
        logger.error(f"sheets_sync: sync_guest_intel falló ({display_id}): {e}")
        return False


async def sync_observacion(result: dict, employee: dict, display_id: str) -> bool:
    try:
        await asyncio.to_thread(_sync_observacion_sync, result, employee, display_id)
        return True
    except Exception as e:
        logger.error(f"sheets_sync: sync_observacion falló ({display_id}): {e}")
        return False


async def sync_reporte(report: dict, items: list[dict], display_id: str) -> bool:
    try:
        await asyncio.to_thread(_sync_reporte_sync, report, items, display_id)
        return True
    except Exception as e:
        logger.error(f"sheets_sync: sync_reporte falló ({display_id}): {e}")
        return False
