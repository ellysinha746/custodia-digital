import uuid
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.session import Base


class VersionObservada(Base):
    """Sprint 4 (historia 14): versión de un archivo con observaciones de otro
    perito. Se guarda APARTE del original y de la copia de trabajo, así nunca
    altera la evidencia y el escaneo de integridad no la confunde."""

    __tablename__ = "versiones_observadas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    archivo_id = Column(UUID(as_uuid=True), ForeignKey("archivos.id"), nullable=False, index=True)
    nombre = Column(String, nullable=False)
    ruta = Column(String, nullable=False)
    hash_sha256 = Column(String, nullable=False)
    observaciones = Column(Text, nullable=False)
    subido_por_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    subido_en = Column(DateTime(timezone=True), server_default=func.now())

    archivo = relationship("Archivo")
    subido_por = relationship("Usuario")