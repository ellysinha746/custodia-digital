import uuid
import enum
from sqlalchemy import Column, String, Boolean, Integer, DateTime, Enum, func
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
    
    # Sprint 6 (historia 25): cuenta pedida desde "Solicitar acceso".
    #   None → cuenta normal · "pendiente" → espera aprobación del jefe · "rechazada"
    estado_solicitud = Column(String, nullable=True)
    
    # Sprint 6 (historia 27): bloqueo temporal tras varios intentos fallidos de login.
    intentos_fallidos = Column(Integer, nullable=False, default=0, server_default="0")
    bloqueado_hasta = Column(DateTime(timezone=True), nullable=True)

    # Sprint 6 (historia 24): segundo factor con TOTP (Google Authenticator, Authy...).
    totp_secreto = Column(String, nullable=True)      # se guarda al empezar a configurarlo
    totp_activo = Column(Boolean, nullable=False, default=False, server_default="false")
    totp_ultimo_paso = Column(Integer, nullable=True)  # evita reutilizar el mismo código
    # Va dentro de los tokens; al subirla (p. ej. al reiniciar el 2FA) se cierran todas las sesiones abiertas.
    sesion_version = Column(Integer, nullable=False, default=0, server_default="0")
