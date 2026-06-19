"""Typed entities — replace ad-hoc dicts where it matters.

Why dataclasses instead of plain dicts:
- IDE autocomplete + type-checker errors before runtime
- Self-documenting: the shape of an `Incident` lives in one place
- `from_*()` constructors centralize defensive parsing of optional fields

Adoption is gradual: existing code keeps using dicts; new code or tests can
opt-in via `Employee.from_dict(row)` / `Incident.from_row(row)`.
"""
from dataclasses import dataclass, field
from typing import Optional

from config.enums import IncidentState, Role


@dataclass
class Employee:
    telegram_id: int
    nombre: str
    departamento: str
    idioma: str = "es"
    rol: Role = Role.EMPLEADO

    @classmethod
    def from_dict(cls, d: dict) -> "Employee":
        return cls(
            telegram_id=int(d["telegram_id"]),
            nombre=d.get("nombre", ""),
            departamento=d.get("departamento", ""),
            idioma=d.get("idioma", "es"),
            rol=Role(d.get("rol", Role.EMPLEADO)),
        )

    def to_dict(self) -> dict:
        return {
            "telegram_id": self.telegram_id,
            "nombre": self.nombre,
            "departamento": self.departamento,
            "idioma": self.idioma,
            "rol": self.rol.value,
        }

    @property
    def first_name(self) -> str:
        return self.nombre.split()[0] if self.nombre else ""

    def is_manager(self) -> bool:
        return self.rol in (Role.ENCARGADO, Role.GERENTE_GENERAL)


@dataclass
class Incident:
    id: int
    timestamp: str
    employee_name: str
    descripcion: str
    employee_dept: Optional[str] = None
    ubicacion: Optional[str] = None
    categoria: Optional[str] = None
    prioridad: Optional[str] = None
    estado: IncidentState = IncidentState.NUEVA
    assigned_to_telegram_id: Optional[int] = None
    assigned_at: Optional[str] = None
    closed_at: Optional[str] = None
    resolution_time_minutes: Optional[int] = None
    photo_path: Optional[str] = None
    huesped_afectado: bool = False
    confianza: Optional[float] = None
    _assignee_name: Optional[str] = None  # transient display helper

    @classmethod
    def from_row(cls, row: dict) -> "Incident":
        """Builds an Incident from a SQLite row dict (handles SQLite's int-for-bool quirks)."""
        estado_raw = row.get("estado") or IncidentState.NUEVA
        return cls(
            id=row["id"],
            timestamp=row.get("timestamp", ""),
            employee_name=row.get("employee_name", ""),
            employee_dept=row.get("employee_dept"),
            descripcion=row.get("descripcion") or "",
            ubicacion=row.get("ubicacion"),
            categoria=row.get("categoria"),
            prioridad=row.get("prioridad"),
            estado=IncidentState(estado_raw) if estado_raw else IncidentState.NUEVA,
            assigned_to_telegram_id=row.get("assigned_to_telegram_id"),
            assigned_at=row.get("assigned_at"),
            closed_at=row.get("closed_at"),
            resolution_time_minutes=row.get("resolution_time_minutes"),
            photo_path=row.get("photo_path"),
            huesped_afectado=bool(row.get("huesped_afectado") or 0),
            confianza=row.get("confianza"),
        )

    def is_open(self) -> bool:
        return self.estado != IncidentState.CERRADA

    def is_assigned(self) -> bool:
        return self.assigned_to_telegram_id is not None
