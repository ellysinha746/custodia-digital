from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

from app.models.log_custodia import AccionEnum


class AuditoriaItemOut(BaseModel):
    id: UUID
    fecha: datetime
    accion: AccionEnum
    resultado: Optional[str] = None
    usuario_nombre: str
    archivo_id: UUID
    archivo_nombre: str
    caso_id: UUID
    caso_numero: str
