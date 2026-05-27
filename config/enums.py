"""Enums tipados para evitar magic strings. StrEnum mantiene compat con strings existentes."""
from enum import StrEnum


class IncidentState(StrEnum):
    ABIERTA = "ABIERTA"
    ASIGNADA = "ASIGNADA"
    EN_PROCESO = "EN_PROCESO"
    CERRADA = "CERRADA"


class ReportType(StrEnum):
    INCIDENCIA = "INCIDENCIA"
    GUEST_INTEL = "GUEST_INTEL"
    OBSERVACION = "OBSERVACION"
    NO_REPORTE = "NO_REPORTE"
    ERROR = "ERROR"
    REPORT = "REPORT"


class NotificationMode(StrEnum):
    TODO = "todo"
    CRITICAS = "criticas"
    SOLO_CRITICAS = "solo_criticas"
    NADA = "nada"


class Role(StrEnum):
    EMPLEADO = "EMPLEADO"
    ENCARGADO = "ENCARGADO"
    GERENTE_GENERAL = "GERENTE_GENERAL"


class Priority(StrEnum):
    CRITICA = "CRITICA"
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAJA = "BAJA"
