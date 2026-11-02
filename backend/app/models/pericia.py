import uuid
from sqlalchemy import Column, String, Text, Integer, Boolean, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.session import Base

# Sprint 5 (épica H19): procedimiento pericial según el CPP 2004.
#
#   Designada → Emitida → En traslado → Observada → En absolución → Absuelta → Concluida
#                                     └──────────── (sin observaciones) ──────→ Concluida

ESTADOS_PERICIA = {
    "designada": "Designada",
    "emitida": "Pericia emitida",
    "en_traslado": "En traslado",
    "observada": "Observada",
    "en_absolucion": "En absolución",
    "absuelta": "Absuelta",
    "concluida": "Concluida",
}


class Pericia(Base):
    __tablename__ = "pericias"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    caso_id = Column(UUID(as_uuid=True), ForeignKey("casos.id"), nullable=False, index=True)
    codigo = Column(String, nullable=False, unique=True)  # PER-2026-0001
    estado = Column(String, nullable=False, default="designada", index=True)
    especialidad = Column(String, nullable=True)  # en qué especialidad del caso se hace la pericia

    # Historia 19.3: designación por el fiscal
    disposicion_fiscal = Column(String, nullable=False)  # N° de disposición / oficio
    objetivos = Column(JSONB, nullable=False)  # [{"texto": ..., "conclusion": ...}]
    plazo_dias = Column(Integer, nullable=False)
    fecha_limite = Column(DateTime(timezone=True), nullable=False)
    designada_por_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    designada_en = Column(DateTime(timezone=True), server_default=func.now())

    # Historia 19.4: emisión del informe pericial
    informe_nombre = Column(String, nullable=True)
    informe_ruta = Column(String, nullable=True)
    informe_hash = Column(String, nullable=True)
    emitida_en = Column(DateTime(timezone=True), nullable=True)

    # Historias 19.5 y 19.6: traslado, conocimiento, absolución, conclusión
    traslado_en = Column(DateTime(timezone=True), nullable=True)
    traslado_plazo_dias = Column(Integer, nullable=True)
    traslado_vence_en = Column(DateTime(timezone=True), nullable=True)
    conocimiento_en = Column(DateTime(timezone=True), nullable=True)
    absuelta_en = Column(DateTime(timezone=True), nullable=True)
    concluida_en = Column(DateTime(timezone=True), nullable=True)

    caso = relationship("Caso")
    designada_por = relationship("Usuario")
    designaciones = relationship("DesignacionPericia", back_populates="pericia", order_by="DesignacionPericia.designado_en")
    observaciones = relationship("ObservacionPericia", back_populates="pericia", order_by="ObservacionPericia.creada_en")
    eventos = relationship("EventoPericia", back_populates="pericia", order_by="EventoPericia.fecha.desc()")


class DesignacionPericia(Base):
    """Quién trabaja en la pericia: perito oficial o perito de parte.
    Al subrogar, la designación se marca inactiva (NO se borra)."""

    __tablename__ = "designaciones_pericia"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pericia_id = Column(UUID(as_uuid=True), ForeignKey("pericias.id"), nullable=False, index=True)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False, index=True)
    tipo = Column(String, nullable=False)  # oficial | parte
    documento = Column(String, nullable=True)
    designado_por_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    designado_en = Column(DateTime(timezone=True), server_default=func.now())
    activa = Column(Boolean, nullable=False, default=True, server_default="true")

    # Historia 19.8: subrogación
    subrogado_en = Column(DateTime(timezone=True), nullable=True)
    motivo_subrogacion = Column(String, nullable=True)
    documento_subrogacion = Column(String, nullable=True)
    subrogado_por_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)

    pericia = relationship("Pericia", back_populates="designaciones")
    usuario = relationship("Usuario", foreign_keys=[usuario_id])


class ObservacionPericia(Base):
    """Historia 19.5/19.6: observación de la parte y su absolución."""

    __tablename__ = "observaciones_pericia"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pericia_id = Column(UUID(as_uuid=True), ForeignKey("pericias.id"), nullable=False, index=True)
    autor_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    texto = Column(Text, nullable=False)
    anexo_nombre = Column(String, nullable=True)
    anexo_ruta = Column(String, nullable=True)
    anexo_hash = Column(String, nullable=True)
    creada_en = Column(DateTime(timezone=True), server_default=func.now())

    respuesta = Column(Text, nullable=True)
    respondida_por_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    respondida_en = Column(DateTime(timezone=True), nullable=True)

    pericia = relationship("Pericia", back_populates="observaciones")
    autor = relationship("Usuario", foreign_keys=[autor_id])
    respondida_por = relationship("Usuario", foreign_keys=[respondida_por_id])


class EventoPericia(Base):
    """Línea de tiempo de la pericia (designaciones, traslado, consultas del perito de parte, etc.)."""

    __tablename__ = "eventos_pericia"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pericia_id = Column(UUID(as_uuid=True), ForeignKey("pericias.id"), nullable=False, index=True)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    tipo = Column(String, nullable=False)
    detalle = Column(String, nullable=True)
    fecha = Column(DateTime(timezone=True), server_default=func.now())

    pericia = relationship("Pericia", back_populates="eventos")
    usuario = relationship("Usuario")
