import uuid
import enum
from sqlalchemy import Column, String, Enum, ForeignKey, DateTime, Text, Float, Integer, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.session import Base


class EstadoProcesamientoEnum(str, enum.Enum):
    pendiente = "pendiente"
    procesando = "procesando"
    listo = "listo"


class Archivo(Base):
    __tablename__ = "archivos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    caso_id = Column(UUID(as_uuid=True), ForeignKey("casos.id"), nullable=False)
    nombre_original = Column(String, nullable=False)
    ruta_original = Column(String, nullable=False)
    ruta_copia_trabajo = Column(String, nullable=False)
    # Nulo mientras el hash se calcula en segundo plano (archivos pesados, Sprint 2)
    hash_original = Column(String, nullable=True)
    hash_actual = Column(String, nullable=True)
    # Sprint 6 (historia 23): hashes adicionales del ORIGINAL, para cotejar con lo que
    # reportan Cellebrite, FTK Imager, etc. (muchos informes traen MD5 y SHA-1).
    # El SHA-256 (hash_original) sigue siendo el que vigila la integridad.
    hash_sha1 = Column(String, nullable=True)
    hash_md5 = Column(String, nullable=True)
    cotejos = Column(JSONB, nullable=True)  # historial de cotejos con herramientas externas
    # Sprint 7 (historia 28): en grafotecnia, el documento cuestionado (dubitado) o el de
    # autoría conocida que sirve de patrón (indubitado). Nulo = sin clasificar.
    rol_grafotecnico = Column(String, nullable=True)
    # Sprint 7 (historia 29): texto extraído de PDFs e imágenes (OCR con Tesseract, en el servidor).
    #   ocr_estado: pendiente | procesando | listo | sin_texto | error  (nulo = no aplica)
    #   ocr_texto: páginas separadas por un salto de página (\f)
    ocr_estado = Column(String, nullable=True)
    ocr_texto = Column(Text, nullable=True)
    ocr_confianza = Column(Float, nullable=True)   # promedio 0-100 (None si vino de la capa de texto del PDF)
    ocr_paginas = Column(Integer, nullable=True)
    ocr_motor = Column(String, nullable=True)      # p. ej. "tesseract 5.5.0 (spa)" o "capa de texto del PDF"
    ocr_en = Column(DateTime(timezone=True), nullable=True)
    ocr_error = Column(String, nullable=True)
    metadatos = Column(JSONB, nullable=True)
        # Sprint 4 (historia 13): ficha del dispositivo de origen (IMEI, modelo, MAC, SO).
    # Se registra una sola vez y sirve de referencia en verificaciones posteriores.
    ficha_dispositivo = Column(JSONB, nullable=True)
    ficha_registrada_en = Column(DateTime(timezone=True), nullable=True)
    
    # Sprint 6 (historia 20): metadatos extraídos automáticamente al subir
    # (tipo real del archivo, EXIF, ffprobe, PDF). Aparte de `metadatos`, que edita el perito.
    metadatos_tecnicos = Column(JSONB, nullable=True)
    estado_procesamiento = Column(
        Enum(EstadoProcesamientoEnum),
        nullable=False,
        default=EstadoProcesamientoEnum.listo,
        server_default=EstadoProcesamientoEnum.listo.value,
    )
    subido_en = Column(DateTime(timezone=True), server_default=func.now())

    caso = relationship("Caso", back_populates="archivos")