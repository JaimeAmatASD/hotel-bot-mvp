import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.enums import IncidentState
from config.transitions import ACTION_TO_STATE, EXPECTED_FROM, action_target_state


def test_estados_existen():
    assert IncidentState.NUEVA == "NUEVA"
    assert IncidentState.RESUELTA == "RESUELTA"
    assert IncidentState.CANCELADA == "CANCELADA"
    assert not hasattr(IncidentState, "ABIERTA")


def test_action_to_state_cubre_todas_las_acciones():
    assert ACTION_TO_STATE["tomar"] == IncidentState.ASIGNADA
    assert ACTION_TO_STATE["asignar"] == IncidentState.ASIGNADA
    assert ACTION_TO_STATE["reasignar"] == IncidentState.ASIGNADA
    assert ACTION_TO_STATE["reabrir"] == IncidentState.ASIGNADA
    assert ACTION_TO_STATE["comenzar"] == IncidentState.EN_PROCESO
    assert ACTION_TO_STATE["terminado"] == IncidentState.RESUELTA
    assert ACTION_TO_STATE["validar"] == IncidentState.CERRADA
    assert ACTION_TO_STATE["cancelar"] == IncidentState.CANCELADA


def test_expected_from_correctos():
    assert EXPECTED_FROM["comenzar"] == [IncidentState.ASIGNADA]
    assert EXPECTED_FROM["terminado"] == [IncidentState.EN_PROCESO]
    assert EXPECTED_FROM["validar"] == [IncidentState.RESUELTA]
    assert EXPECTED_FROM["reabrir"] == [IncidentState.RESUELTA]
    assert IncidentState.NUEVA in EXPECTED_FROM["cancelar"]
    assert IncidentState.RESUELTA in EXPECTED_FROM["cancelar"]
    assert IncidentState.CERRADA not in EXPECTED_FROM["cancelar"]


def test_action_target_state_helper():
    assert action_target_state("validar") == IncidentState.CERRADA
    assert action_target_state("desconocida") is None
