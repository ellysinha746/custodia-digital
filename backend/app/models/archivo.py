import uuid
import enum
from sqlalchemy import Column, String, Enum, ForeignKey, DateTime, func
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
    metadatos = Column(JSONB, nullable=True)
    estado_procesamiento = Column(
        Enum(EstadoProcesamientoEnum),
        nullable=False,
        default=EstadoProcesamientoEnum.listo,
        server_default=EstadoProcesamientoEnum.listo.value,
    )
    subido_en = Column(DateTime(timezone=True), server_default=func.now())

    caso = relationship("Caso", back_populates="archivos")