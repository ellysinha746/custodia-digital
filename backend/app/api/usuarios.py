from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import hash_password
from app.core.permisos import requiere, ETIQUETAS_ROL
from app.models.caso import Caso
from app.models.usuario import Usuario, RolEnum, EspecialidadEnum

# Sprint 5 (historia 19.1): gestión de usuarios y roles (solo jefe de laboratorio).
router = APIRouter(prefix="/usuarios", tags=["usuarios y roles"])


class UsuarioAdminOut(BaseModel):
    id: UUID
    nombre: str
    email: str
    especialidad: Optional[EspecialidadEnum] = None
    rol: RolEnum
    rol_etiqueta: str
    activo: bool
    casos_a_cargo: int
    creado_en: Optional[datetime] = None
    institucion: Optional[str] = None
    registro_profesional: Optional[str] = None
    telefono: Optional[str] = None


class UsuarioNuevo(BaseModel):
    nombre: str
    email: EmailStr
    password: str
    especialidad: Optional[EspecialidadEnum] = None  # solo para peritos
    rol: RolEnum = RolEnum.perito
    institucion: Optional[str] = None
    registro_profesional: Optional[str] = None
    telefono: Optional[str] = None


class UsuarioCambios(BaseModel):
    nombre: Optional[str] = None
    especialidad: Optional[EspecialidadEnum] = None
    rol: Optional[RolEnum] = None
    activo: Optional[bool] = None
    institucion: Optional[str] = None
    registro_profesional: Optional[str] = None
    telefono: Optional[str] = None


class RolOut(BaseModel):
    valor: RolEnum
    etiqueta: str


def _a_salida(u: Usuario, casos: int) -> UsuarioAdminOut:
    return UsuarioAdminOut(
        id=u.id,
        nombre=u.nombre,
        email=u.email,
        especialidad=u.especialidad,
        rol=u.rol,
        rol_etiqueta=ETIQUETAS_ROL.get(u.rol, u.rol.value),
        activo=u.activo,
        casos_a_cargo=casos,
        creado_en=u.creado_en,
        institucion=u.institucion,
        registro_profesional=u.registro_profesional,
        telefono=u.telefono,
    )


def _casos_por_usuario(db: Session) -> dict:
    return dict(
        db.query(Caso.usuario_id, func.count())
        .filter(Caso.eliminado_en.is_(None))
        .group_by(Caso.usuario_id)
        .all()
    )


ROLES_CON_ESPECIALIDAD = (RolEnum.perito, RolEnum.perito_parte)


def _especialidad_segun_rol(rol: RolEnum, especialidad):
    """Sprint 5: solo los peritos tienen especialidad; el fiscal y el jefe no."""
    if rol in ROLES_CON_ESPECIALIDAD:
        if not especialidad:
            raise HTTPException(status_code=400, detail="Indica la especialidad del perito.")
        return especialidad
    return None


@router.get("/roles", response_model=List[RolOut])
def listar_roles(usuario_actual=Depends(requiere("gestionar_usuarios"))):
    return [RolOut(valor=r, etiqueta=e) for r, e in ETIQUETAS_ROL.items()]


@router.get("", response_model=List[UsuarioAdminOut])
def listar_usuarios(
    db: Session = Depends(get_db),
    usuario_actual=Depends(requiere("gestionar_usuarios")),
):
    conteo = _casos_por_usuario(db)
    usuarios = db.query(Usuario).order_by(Usuario.activo.desc(), Usuario.nombre).all()
    return [_a_salida(u, conteo.get(u.id, 0)) for u in usuarios]


@router.post("", response_model=UsuarioAdminOut, status_code=status.HTTP_201_CREATED)
def crear_usuario(
    payload: UsuarioNuevo,
    db: Session = Depends(get_db),
    usuario_actual=Depends(requiere("gestionar_usuarios")),
):
    if db.query(Usuario).filter(Usuario.email == payload.email).first():
        raise HTTPException(status_code=409, detail="El email ya está registrado.")
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres.")
    especialidad = _especialidad_segun_rol(payload.rol, payload.especialidad)
    nuevo = Usuario(
        nombre=payload.nombre.strip(),
        email=payload.email,
        password_hash=hash_password(payload.password),
        especialidad=especialidad,
        rol=payload.rol,
        institucion=(payload.institucion or "").strip() or None,
        registro_profesional=(payload.registro_profesional or "").strip() or None,
        telefono=(payload.telefono or "").strip() or None,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return _a_salida(nuevo, 0)


@router.patch("/{usuario_id}", response_model=UsuarioAdminOut)
def actualizar_usuario(
    usuario_id: UUID,
    payload: UsuarioCambios,
    db: Session = Depends(get_db),
    usuario_actual=Depends(requiere("gestionar_usuarios")),
):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    if usuario.id == usuario_actual.id:
        # Evita que el jefe de laboratorio se bloquee a sí mismo.
        if payload.rol is not None and payload.rol != usuario.rol:
            raise HTTPException(status_code=400, detail="No puedes cambiar tu propio rol.")
        if payload.activo is False:
            raise HTTPException(status_code=400, detail="No puedes desactivar tu propio usuario.")

    if payload.nombre is not None:
        usuario.nombre = payload.nombre.strip()
    if payload.especialidad is not None:
        usuario.especialidad = payload.especialidad
    if payload.rol is not None:
        usuario.rol = payload.rol
    # Un perito siempre tiene especialidad; el fiscal y el jefe, ninguna.
    usuario.especialidad = _especialidad_segun_rol(usuario.rol, payload.especialidad or usuario.especialidad)
    if payload.activo is not None:
        usuario.activo = payload.activo
    for campo in ("institucion", "registro_profesional", "telefono"):
        valor = getattr(payload, campo)
        if valor is not None:
            setattr(usuario, campo, valor.strip() or None)

    # Siempre debe quedar al menos un jefe de laboratorio activo.
    db.flush()  # la sesión no hace autoflush: hay que mandar los cambios antes de contar
    admins_activos = db.query(Usuario).filter(Usuario.rol == RolEnum.admin, Usuario.activo.is_(True)).count()
    if admins_activos == 0:
        db.rollback()
        raise HTTPException(status_code=400, detail="Debe quedar al menos un jefe de laboratorio activo.")

    db.commit()
    db.refresh(usuario)
    return _a_salida(usuario, _casos_por_usuario(db).get(usuario.id, 0))
