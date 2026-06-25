"""Máquina de estados de incidencias: única fuente de verdad de transiciones.

Cada acción (verbo del callback) mapea a un estado destino y a la lista de
estados de origen permitidos. `asignar`/`reasignar` abren el selector de persona;
la transición real ocurre vía la acción `assign_to` (ver callback_handler)."""
from config.enums import IncidentState

# Estado destino de cada acción
ACTION_TO_STATE = {
    "tomar":     IncidentState.ASIGNADA,
    "asignar":   IncidentState.ASIGNADA,
    "reasignar": IncidentState.ASIGNADA,
    "reabrir":   IncidentState.ASIGNADA,
    "comenzar":  IncidentState.EN_PROCESO,
    "terminado": IncidentState.RESUELTA,
    "validar":   IncidentState.CERRADA,
    "cancelar":  IncidentState.CANCELADA,
}

# Estados de origen válidos por acción
EXPECTED_FROM = {
    "tomar":     [IncidentState.NUEVA],
    "asignar":   [IncidentState.NUEVA, IncidentState.ASIGNADA, IncidentState.EN_PROCESO],
    "reasignar": [IncidentState.ASIGNADA, IncidentState.EN_PROCESO],
    "reabrir":   [IncidentState.RESUELTA],
    "comenzar":  [IncidentState.ASIGNADA],
    # 'comenzar' (EN_PROCESO) es opcional: se puede terminar directo desde ASIGNADA
    "terminado": [IncidentState.EN_PROCESO, IncidentState.ASIGNADA],
    "validar":   [IncidentState.RESUELTA],
    "cancelar":  [IncidentState.NUEVA, IncidentState.ASIGNADA,
                  IncidentState.EN_PROCESO, IncidentState.RESUELTA],
}

# Acciones que requieren rol manager (gestión) vs. ejecutor
MANAGEMENT_ACTIONS = {"asignar", "tomar", "reasignar", "validar", "reabrir", "cancelar"}
EXECUTION_ACTIONS = {"comenzar", "terminado"}

# Estados terminales (sin botones)
TERMINAL_STATES = {IncidentState.CERRADA, IncidentState.CANCELADA}


def action_target_state(action: str):
    """Estado destino de una acción, o None si la acción es desconocida."""
    return ACTION_TO_STATE.get(action)
