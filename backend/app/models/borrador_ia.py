import uuid
from sqlalchemy import Column, String, Text, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.session import Base


class BorradorIA(Base):
    """Sprint 7 (historia 34): borrador DESCRIPTIVO del cotejo grafotécnico redactado con IA.

    Es material de apoyo: nunca dictamina autenticidad. El perito lo revisa, lo corrige y lo
    firma; desde ahí queda inmutable (hash + sello HMAC). Se guarda qué se envió al proveedor
    de IA, con qué modelo y cuándo, y el texto original de la IA junto al texto revisado."""

    __tablename__ = "borradores_ia"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    caso_id = Column(UUID(as_uuid=True), ForeignKey("casos.id"), nullable=False, index=True)
    generado_por_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    generado_en = Column(DateTime(timezone=True), nullable=False)
    modelo_solicitado = Column(String, nullable=False)
    modelo_respondio = Column(String, nullable=True)   # puede ser otro si actuó el fallback
    request_id = Column(String, nullable=True)          # id de la petición en el proveedor (auditoría)
    texto_generado = Column(Text, nullable=False)        # lo que escribió la IA, tal cual (nunca cambia)
    texto = Column(Text, nullable=False)                 # lo que revisa y firma el perito
    documentos = Column(JSONB, nullable=False)           # qué documentos se usaron (id, rol, SHA-256)
    enviado = Column(JSONB, nullable=False)              # qué salió del laboratorio y a quién
    tokens_entrada = Column(Integer, nullable=True)
    tokens_salida = Column(Integer, nullable=True)
    estado = Column(String, nullable=False, default="borrador")  # borrador | firmado
    firmado_por_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    firmado_en = Column(DateTime(timezone=True), nullable=True)
    hash_texto = Column(String, nullable=True)
    firma_hmac = Column(String, nullable=True)

    generado_por = relationship("Usuario", foreign_keys=[generado_por_id])
    firmado_por = relationship("Usuario", foreign_keys=[firmado_por_id])
