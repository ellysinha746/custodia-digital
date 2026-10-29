from pydantic import BaseModel, EmailStr
from uuid import UUID
from app.models.usuario import EspecialidadEnum, RolEnum

class UsuarioCreate(BaseModel):
    nombre: str
    email: EmailStr
    password: str
    especialidad: EspecialidadEnum

class UsuarioOut(BaseModel):
    id: UUID
    nombre: str
    email: EmailStr
    especialidad: EspecialidadEnum
    rol: RolEnum

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str