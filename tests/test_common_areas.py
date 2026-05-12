"""Tests for is_location_complete (Sprint A.2.6)."""
import pytest
from config.rules import is_location_complete


@pytest.mark.parametrize("ubicacion", [
    "Habitación 204",
    "hab. 305 baño",
    "Lobby",
    "lobby cerca de recepción",
    "alfombra del lobby",
    "ducha del spa",
    "Spa",
    "Piscina exterior",
])
def test_complete_locations(ubicacion):
    assert is_location_complete(ubicacion) is True


@pytest.mark.parametrize("ubicacion", [
    "una habitación",
    "habitación",
    "baño",
    None,
    "",
])
def test_incomplete_locations(ubicacion):
    assert is_location_complete(ubicacion) is False
