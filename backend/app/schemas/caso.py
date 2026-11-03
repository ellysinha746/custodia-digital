from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import List, Optional
from app.models.usuario import EspecialidadEnum
from app.models.caso import EstadoCasoEnum

class CasoCreate(BaseModel):
    numero_caso: str
    # Sprint 5: una o varias especialidades. `especialidad` se acepta por compatibilidad.
    especialidades: Optional[List[EspecialidadEnum]] = None
    especialidad: Optional[EspecialidadEnum] = None

class CasoOut(BaseModel):
    id: UUID
    numero_caso: str
    especialidad: EspecialidadEnum
    especialidades: List[EspecialidadEnum] = []
    estado: EstadoCasoEnum
    usuario_id: UUID
    creado_en: datetime

    class Config:
        from_attributes = True


class CasoEstadoUpdate(BaseModel):
    estado: EstadoCasoEnum


class CasoPapeleraOut(CasoOut):
    eliminado_en: datetime
    dias_restantes: int
