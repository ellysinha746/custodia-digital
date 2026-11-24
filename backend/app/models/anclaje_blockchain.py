import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, LargeBinary
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.session import Base


class AnclajeBlockchain(Base):
    """Sprint 8 (historia 39): anclaje del historial de custodia en Bitcoin con OpenTimestamps.

    Se guarda la huella SHA-256 de TODO el historial de custodia hasta un momento ("hasta") y la
    prueba .ots que devuelven los calendarios de OpenTimestamps. En unas horas la huella queda
    dentro de un bloque de Bitcoin: desde ahí nadie (ni el administrador) puede cambiar un registro
    anterior sin que la verificación lo detecte."""

    __tablename__ = "anclajes_blockchain"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    creado_en = Column(DateTime(timezone=True), nullable=False)
    creado_por_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)  # vacío = automático
    hasta = Column(DateTime(timezone=True), nullable=False)
    total_registros = Column(Integer, nullable=False)
    huella = Column(String(64), nullable=False)          # SHA-256 del historial (hex)
    prueba_ots = Column(LargeBinary, nullable=False)     # archivo .ots
    calendarios = Column(JSONB, nullable=False)          # calendarios que aceptaron la huella
    estado = Column(String(20), nullable=False, default="pendiente")  # pendiente | confirmado
    bloque_bitcoin = Column(Integer, nullable=True)
    actualizado_en = Column(DateTime(timezone=True), nullable=True)

    creado_por = relationship("Usuario")
