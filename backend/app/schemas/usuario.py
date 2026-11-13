from typing import Literal, Optional
from pydantic import BaseModel, EmailStr
from uuid import UUID
from app.models.usuario import EspecialidadEnum, RolEnum

class UsuarioCreate(BaseModel):
    """Sprint 6 (historia 25): solicitud de cuenta desde "Solicitar acceso".
    Solo se puede pedir una cuenta de perito; el jefe de laboratorio la aprueba."""
    nombre: str
    email: EmailStr
    password: str
    especialidad: EspecialidadEnum
    rol: Literal["perito", "perito_parte"] = "perito"
    institucion: Optional[str] = None
    registro_profesional: Optional[str] = None
    telefono: Optional[str] = None

class UsuarioOut(BaseModel):
    id: UUID
    nombre: str
    email: EmailStr
    especialidad: Optional[EspecialidadEnum] = None
    rol: RolEnum
    activo: bool = True
    institucion: Optional[str] = None
    registro_profesional: Optional[str] = None
    telefono: Optional[str] = None
    estado_solicitud: Optional[str] = None
    totp_activo: bool = False  # Sprint 6 (historia 24)

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    recordarme: bool = False  # Sprint 6 (historia 25): sesión persistente

class TokenResponse(BaseModel):
    # Sprint 6 (historia 24): si falta el código de 2FA no hay tokens de sesión todavía,
    # solo `token_2fa` (y `configurar_2fa` si el usuario aún no escanea su QR).
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    requiere_2fa: bool = False
    configurar_2fa: bool = False
    token_2fa: Optional[str] = None

# Sprint 6 (historia 24): pasos de la verificación en dos pasos.
class Token2FA(BaseModel):
    token_2fa: str

class Codigo2FA(BaseModel):
    token_2fa: str
    codigo: str

class Configuracion2FA(BaseModel):
    secreto: str   # por si no se puede escanear el QR y hay que escribirlo a mano
    uri: str       # otpauth://totp/...
    qr: str        # imagen PNG como data URI

class RefreshRequest(BaseModel):
    refresh_token: str