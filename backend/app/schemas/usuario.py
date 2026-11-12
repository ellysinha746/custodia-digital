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

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    recordarme: bool = False  # Sprint 6 (historia 25): sesión persistente

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str