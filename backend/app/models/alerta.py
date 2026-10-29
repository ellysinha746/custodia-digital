import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.session import Base


class Alerta(Base):
    """Sprint 4 (historia 12): se genera cuando el hash de un archivo cambió
    sin un registro de custodia que lo respalde."""

    __tablename__ = "alertas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    archivo_id = Column(UUID(as_uuid=True), ForeignKey("archivos.id"), nullable=False, index=True)
    caso_id = Column(UUID(as_uuid=True), ForeignKey("casos.id"), nullable=False, index=True)
    tipo = Column(String, nullable=False, default="hash_sin_respaldo")
    ubicacion = Column(String, nullable=False)  # original | copia | ambos
    hash_esperado = Column(String, nullable=True)
    hash_encontrado = Column(String, nullable=True)  # None = el archivo ya no existe en disco
    detalle = Column(String, nullable=False)
    origen = Column(String, nullable=False)  # verificacion_manual | escaneo_automatico
    correo_enviado = Column(Boolean, nullable=False, default=False, server_default="false")
    creada_en = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    atendida_en = Column(DateTime(timezone=True), nullable=True)
    atendida_por_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    nota_atencion = Column(String, nullable=True)

    archivo = relationship("Archivo")
    caso = relationship("Caso")
    atendida_por = relationship("Usuario")