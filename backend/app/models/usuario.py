import uuid
import enum
from sqlalchemy import Column, String, Enum, DateTime, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from app.db.session import Base

class EspecialidadEnum(str, enum.Enum):
    audio = "audio"
    video = "video"
    informatica = "informatica"
    telefonia = "telefonia"

class RolEnum(str, enum.Enum):
    perito = "perito"            # Perito oficial
    admin = "admin"              # Jefe de laboratorio
    perito_parte = "perito_parte"  # Sprint 5: perito de parte (CPP art. 177)
    fiscal = "fiscal"            # Sprint 5: fiscal / auditor, solo lectura

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    especialidad = Column(Enum(EspecialidadEnum), nullable=True)  # Sprint 5: solo los peritos tienen especialidad
    rol = Column(Enum(RolEnum), nullable=False, default=RolEnum.perito)
    membrete_logo_url = Column(String, nullable=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())
    # Sprint 5 (historia 19.1): un usuario desactivado no puede iniciar sesión,
    # pero no se borra: su participación queda en la cadena de custodia.
    activo = Column(Boolean, nullable=False, default=True, server_default="true")

    # Sprint 5 (historia 19.2): ficha profesional del perito (padrón de peritos).
    institucion = Column(String, nullable=True)            # DIRCRI PNP, Medicina Legal, Laboratorio MP...
    registro_profesional = Column(String, nullable=True)   # N° de registro / colegiatura
    telefono = Column(String, nullable=True)
