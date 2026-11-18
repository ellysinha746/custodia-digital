import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.session import Base


class AnalisisFirma(Base):
    """Sprint 7 (historia 30): análisis comparativo de firmas con OpenCV.

    Es una herramienta de APOYO al perito grafotécnico: mide y compara, no dictamina.
    Se guarda qué firmas se usaron (archivo, página y recorte), el resultado numérico y su
    SHA-256, para poder repetir el análisis y demostrar que el resultado no se alteró."""

    __tablename__ = "analisis_firmas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    caso_id = Column(UUID(as_uuid=True), ForeignKey("casos.id"), nullable=False, index=True)
    realizado_por_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    realizado_en = Column(DateTime(timezone=True), nullable=False)
    dubitada_id = Column(UUID(as_uuid=True), ForeignKey("archivos.id"), nullable=False)
    entradas = Column(JSONB, nullable=False)        # [{archivo_id, rol, nombre, sha256, pagina, recorte}]
    resultado = Column(JSONB, nullable=False)       # métricas y comparaciones (sin imágenes)
    hash_resultado = Column(String, nullable=False)

    realizado_por = relationship("Usuario")
