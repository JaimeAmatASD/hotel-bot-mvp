"""Tests para Sprint B.2 — notificaciones."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Test 12: generate_display_id
# ---------------------------------------------------------------------------

def test_generate_display_id_incidencia():
    from storage import generate_display_id
    assert generate_display_id("INCIDENCIA", 1) == "INC-001"
    assert generate_display_id("INCIDENCIA", 42) == "INC-042"


def test_generate_display_id_otros_tipos():
    from storage import generate_display_id
    assert generate_display_id("OBSERVACION", 15) == "OBS-015"
    assert generate_display_id("GUEST_INTEL", 8) == "MEM-008"
    assert generate_display_id("NO_REPORTE", 3) == "NR-003"
