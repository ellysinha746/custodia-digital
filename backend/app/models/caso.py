import uuid
import enum
from sqlalchemy import Column, String, Enum, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.usuario import EspecialidadEnum

class EstadoCasoEnum(str, enum.Enum):
    abierto = "abierto"
    en_proceso = "en_proceso"
    cerrado = "cerrado"

class Caso(Base):
    __tablename__ = "casos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    numero_caso = Column(String, nullable=False, unique=True)
    especialidad = Column(Enum(EspecialidadEnum), nullable=False)
    estado = Column(Enum(EstadoCasoEnum), nullable=False, default=EstadoCasoEnum.abierto, index=True)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())
    eliminado_en = Column(DateTime(timezone=True), nullable=True, index=True)

    usuario = relationship("Usuario")
    archivos = relationship("Archivo", back_populates="caso")