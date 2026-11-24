from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, Any, Dict, List

from pydantic import Field

from app.models.archivo import EstadoProcesamientoEnum
from app.models.log_custodia import AccionEnum


class ArchivoOut(BaseModel):
    id: UUID
    caso_id: UUID
    nombre_original: str
    hash_original: Optional[str] = None
    hash_actual: Optional[str] = None
    hash_sha1: Optional[str] = None  # Sprint 6 (historia 23)
    hash_md5: Optional[str] = None
    cotejos: Optional[List[Dict[str, Any]]] = None
    rol_grafotecnico: Optional[str] = None  # Sprint 7 (historia 28): dubitado | indubitado
    # Sprint 7 (historia 29): estado del OCR (el texto completo va en GET /archivos/{id}/ocr)
    ocr_estado: Optional[str] = None
    ocr_confianza: Optional[float] = None
    ocr_paginas: Optional[int] = None
    ocr_motor: Optional[str] = None
    ocr_en: Optional[datetime] = None
    ocr_error: Optional[str] = None
    # Sprint 8 (historia 40): estado de la transcripción (el texto va en GET /archivos/{id}/transcripcion)
    transcripcion_estado: Optional[str] = None
    transcripcion_duracion: Optional[float] = None
    transcripcion_motor: Optional[str] = None
    transcripcion_en: Optional[datetime] = None
    transcripcion_error: Optional[str] = None
    metadatos: Optional[Any] = None
    estado_procesamiento: EstadoProcesamientoEnum
    subido_en: datetime
    ficha_dispositivo: Optional[Dict[str, Any]] = None
    ficha_registrada_en: Optional[datetime] = None
    metadatos_tecnicos: Optional[Dict[str, Any]] = None  # Sprint 6 (historia 20)

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

# Sprint 6 (historia 23): cotejo del hash con el informe de una herramienta forense.
class CotejoIn(BaseModel):
    herramienta: str = Field(..., min_length=1, max_length=80)        # Cellebrite UFED, FTK Imager...
    texto: str = Field(..., min_length=32, max_length=20000)          # hash suelto o bloque del informe
    referencia: Optional[str] = Field(None, max_length=200)           # N° de informe / extracción


class HashCotejado(BaseModel):
    algoritmo: str          # md5 | sha1 | sha256
    valor: str              # el que trae el informe
    esperado: str           # el que tiene CustodiaDigital
    coincide: bool


class CotejoOut(BaseModel):
    resultado: str          # coincide | parcial | no_coincide
    mensaje: str
    herramienta: str
    referencia: Optional[str] = None
    hashes: List[HashCotejado]
    alerta_id: Optional[UUID] = None
    cotejado_en: datetime


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
