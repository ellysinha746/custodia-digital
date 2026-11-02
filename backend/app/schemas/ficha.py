from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class FichaDispositivoIn(BaseModel):
    """Datos del dispositivo de origen. Todos opcionales, pero al menos uno."""
    imei: Optional[str] = None
    modelo: Optional[str] = None
    mac: Optional[str] = None
    sistema_operativo: Optional[str] = None


class CampoComparado(BaseModel):
    campo: str
    etiqueta: str
    registrado: Optional[str] = None
    actual: Optional[str] = None
    estado: str  # coincide | distinto | no_verificado | sin_registro


class VerificacionDispositivoOut(BaseModel):
    archivo_id: UUID
    resultado: str  # dispositivo_coincide | dispositivo_distinto
    campos: List[CampoComparado]
    alerta_id: Optional[UUID] = None
    verificado_en: datetime