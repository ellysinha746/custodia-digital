import uuid
import enum
from sqlalchemy import Column, String, Enum, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.session import Base

class AccionEnum(str, enum.Enum):
    subida = "subida"
    acceso = "acceso"
    descarga = "descarga"
    verificacion = "verificacion"

class LogCustodia(Base):
    __tablename__ = "logs_custodia"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    archivo_id = Column(UUID(as_uuid=True), ForeignKey("archivos.id"), nullable=False)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    accion = Column(Enum(AccionEnum), nullable=False)
    resultado = Column(String, nullable=True)
    fecha = Column(DateTime(timezone=True), server_default=func.now())

    archivo = relationship("Archivo")
    usuario = relationship("Usuario")