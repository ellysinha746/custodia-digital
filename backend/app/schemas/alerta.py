from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class AlertaOut(BaseModel):
    id: UUID
    archivo_id: UUID
    archivo_nombre: str
    caso_id: UUID
    caso_numero: str
    tipo: str
    ubicacion: str
    hash_esperado: Optional[str] = None
    hash_encontrado: Optional[str] = None
    detalle: str
    origen: str
    correo_enviado: bool
    creada_en: datetime
    atendida_en: Optional[datetime] = None
    atendida_por_nombre: Optional[str] = None
    nota_atencion: Optional[str] = None


class AtenderAlertaIn(BaseModel):
    nota: Optional[str] = None


class ResumenAlertasOut(BaseModel):
    pendientes: int


class EscaneoOut(BaseModel):
    archivos_revisados: int
    alertas_nuevas: int