"""Tests for Sprint B.8: Google Sheets sync layer — gspread fully mocked, no network."""
import pytest
from unittest.mock import MagicMock, patch
import sheets_sync


def _make_ws_mock(col_a_values=None):
    ws = MagicMock()
    ws.col_values.return_value = col_a_values or []
    ws.row_values.return_value = []
    return ws


@pytest.fixture(autouse=True)
def reset_cache():
    sheets_sync._client = None
    sheets_sync._spreadsheet = None
    sheets_sync._worksheets.clear()
    yield
    sheets_sync._client = None
    sheets_sync._spreadsheet = None
    sheets_sync._worksheets.clear()


# T1: sync_incidencia con ID nuevo → append
@pytest.mark.asyncio
async def test_sync_incidencia_new_id_appends():
    ws = _make_ws_mock(col_a_values=["ID"])
    with patch.object(sheets_sync, "_get_worksheet", return_value=ws):
        result = await sheets_sync.sync_incidencia(
            {"employee_name": "Ana", "estado": "ABIERTA", "timestamp": "2024-01-01"},
            "INC-001",
        )
    assert result is True
    ws.append_row.assert_called_once()
    ws.update.assert_not_called()


# T2: sync_incidencia con ID existente → update, no append
@pytest.mark.asyncio
async def test_sync_incidencia_existing_id_updates():
    ws = _make_ws_mock(col_a_values=["ID", "INC-001"])
    with patch.object(sheets_sync, "_get_worksheet", return_value=ws):
        result = await sheets_sync.sync_incidencia(
            {"employee_name": "Ana", "estado": "ASIGNADA", "timestamp": "2024-01-01"},
            "INC-001",
        )
    assert result is True
    ws.update.assert_called_once()
    ws.append_row.assert_not_called()


# T3: sync_guest_intel → append correcto
@pytest.mark.asyncio
async def test_sync_guest_intel_appends():
    ws = _make_ws_mock()
    with patch.object(sheets_sync, "_get_worksheet", return_value=ws):
        result = await sheets_sync.sync_guest_intel(
            {"descripcion": "Prefiere almohada blanda", "habitacion_huesped": "204"},
            {"nombre": "María", "departamento": "HK"},
            "MEM-001",
        )
    assert result is True
    ws.append_row.assert_called_once()
    args = ws.append_row.call_args[0][0]
    assert args[0] == "MEM-001"


# T4: sync_observacion → append correcto
@pytest.mark.asyncio
async def test_sync_observacion_appends():
    ws = _make_ws_mock()
    with patch.object(sheets_sync, "_get_worksheet", return_value=ws):
        result = await sheets_sync.sync_observacion(
            {"descripcion": "El lobby huele a humedad", "categoria": "MANTENIMIENTO"},
            {"nombre": "Carlos", "departamento": "MANTENIMIENTO"},
            "OBS-001",
        )
    assert result is True
    ws.append_row.assert_called_once()


# T5: sync_reporte → append con desglose correcto
@pytest.mark.asyncio
async def test_sync_reporte_appends_with_desglose():
    ws = _make_ws_mock()
    items = [
        {"tipo": "INCIDENCIA"}, {"tipo": "INCIDENCIA"},
        {"tipo": "GUEST_INTEL"}, {"tipo": "OBSERVACION"},
    ]
    with patch.object(sheets_sync, "_get_worksheet", return_value=ws):
        result = await sheets_sync.sync_reporte(
            {"employee_name": "Ana", "closed_at": "2024-01-01T12:00:00"},
            items,
            "REP-001",
        )
    assert result is True
    ws.append_row.assert_called_once()
    row = ws.append_row.call_args[0][0]
    assert row[0] == "REP-001"
    assert "2 INC" in row[4]
    assert "1 GI" in row[4]
    assert "1 OBS" in row[4]


# T6: gspread lanza excepción → devuelve False, no propaga
@pytest.mark.asyncio
async def test_sync_exception_returns_false_no_raise():
    ws = _make_ws_mock()
    ws.append_row.side_effect = Exception("Network error")
    with patch.object(sheets_sync, "_get_worksheet", return_value=ws):
        result = await sheets_sync.sync_guest_intel(
            {}, {"nombre": "Ana"}, "MEM-002"
        )
    assert result is False


# T7: ensure_headers en hoja vacía → escribe encabezados
def test_ensure_headers_empty_sheet_writes_headers():
    ws_mocks = {name: _make_ws_mock() for name in sheets_sync._HEADERS}
    with patch.object(sheets_sync, "_get_worksheet", side_effect=lambda n: ws_mocks[n]):
        sheets_sync.ensure_headers()
    for name, ws in ws_mocks.items():
        ws.insert_row.assert_called_once_with(sheets_sync._HEADERS[name], 1)


# T8: ensure_headers en hoja con encabezados existentes → no duplica
def test_ensure_headers_existing_headers_no_duplicate():
    ws_mocks = {}
    for name in sheets_sync._HEADERS:
        ws = _make_ws_mock()
        ws.row_values.return_value = sheets_sync._HEADERS[name]
        ws_mocks[name] = ws

    with patch.object(sheets_sync, "_get_worksheet", side_effect=lambda n: ws_mocks[n]):
        sheets_sync.ensure_headers()

    for ws in ws_mocks.values():
        ws.insert_row.assert_not_called()
