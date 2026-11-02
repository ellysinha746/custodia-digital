import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.session import Base


class ReporteAuditoria(Base):
    """Sprint 4 (historia 16): registro de cada reporte de auditoría exportado.
    Guarda el hash del archivo entregado y su sello de tiempo firmado, para
    poder comprobar después que un reporte es auténtico y no fue editado."""

    __tablename__ = "reportes_auditoria"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    folio = Column(String, nullable=False, unique=True)
    formato = Column(String, nullable=False)  # pdf | csv
    filtros = Column(JSONB, nullable=True)
    total_eventos = Column(Integer, nullable=False)
    hash_contenido = Column(String, nullable=False)  # SHA-256 de los eventos incluidos
    hash_archivo = Column(String, nullable=False, index=True)  # SHA-256 del archivo entregado
    firma = Column(String, nullable=False)  # HMAC-SHA256 (folio | fecha | hash_contenido)
    generado_en = Column(DateTime(timezone=True), nullable=False)
    generado_por_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)

    generado_por = relationship("Usuario")