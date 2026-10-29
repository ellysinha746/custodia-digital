import uuid
import enum
from sqlalchemy import Column, String, Enum, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from app.db.session import Base

class EspecialidadEnum(str, enum.Enum):
    audio = "audio"
    video = "video"
    informatica = "informatica"
    telefonia = "telefonia"

class RolEnum(str, enum.Enum):
    perito = "perito"
    admin = "admin"

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    especialidad = Column(Enum(EspecialidadEnum), nullable=False)
    rol = Column(Enum(RolEnum), nullable=False, default=RolEnum.perito)
    membrete_logo_url = Column(String, nullable=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())