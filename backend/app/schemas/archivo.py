from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, Any, Dict

from app.models.archivo import EstadoProcesamientoEnum
from app.models.log_custodia import AccionEnum


class ArchivoOut(BaseModel):
    id: UUID
    caso_id: UUID
    nombre_original: str
    hash_original: Optional[str] = None
    hash_actual: Optional[str] = None
    metadatos: Optional[Any] = None
    estado_procesamiento: EstadoProcesamientoEnum
    subido_en: datetime
    ficha_dispositivo: Optional[Dict[str, Any]] = None
    ficha_registrada_en: Optional[datetime] = None

    class Config:
        from_attributes = True


class MetadatosUpdate(BaseModel):
    metadatos: Dict[str, Any]


class VerificacionOut(BaseModel):
    archivo_id: UUID
    resultado: str  # "integro" | "alterado"
    hash_original: str
    hash_actual: Optional[str] = None  # hash del original hoy (None = ya no existe)
    hash_copia: Optional[str] = None   # hash de la copia de trabajo hoy
    alerta_id: Optional[UUID] = None   # alerta generada en esta verificación, si hubo
    verificado_en: datetime

class LogCustodiaOut(BaseModel):
    id: UUID
    archivo_id: UUID
    usuario_id: UUID
    usuario_nombre: str
    accion: AccionEnum
    resultado: Optional[str] = None
    fecha: datetime

    class Config:
        from_attributes = True
