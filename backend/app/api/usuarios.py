from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.session import get_db
from app.core.security import hash_password, validar_password
from app.core.permisos import requiere, ETIQUETAS_ROL
from app.models.caso import Caso
from app.models.usuario import Usuario, RolEnum, EspecialidadEnum
from app.services.correo_service import enviar_correo

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
    estado_solicitud: Optional[str] = None  # Sprint 6 (historia 25)
    bloqueado_hasta: Optional[datetime] = None  # Sprint 6 (historia 27)
    totp_activo: bool = False  # Sprint 6 (historia 24)


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
        estado_solicitud=u.estado_solicitud,
        bloqueado_hasta=u.bloqueado_hasta,
        totp_activo=bool(u.totp_activo),
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
    validar_password(payload.password)  # Sprint 6 (historia 27)
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
        if usuario.estado_solicitud and payload.activo:
            raise HTTPException(status_code=400, detail="Esta cuenta es una solicitud: usa Aprobar para habilitarla.")
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




# ---------------------------------------------------------------------------
# Sprint 6 (historia 25): solicitudes de cuenta con aprobación del jefe.

class Aprobacion(BaseModel):
    rol: RolEnum = RolEnum.perito
    especialidad: Optional[EspecialidadEnum] = None


class Rechazo(BaseModel):
    motivo: Optional[str] = None


def _solicitud(db: Session, usuario_id: UUID) -> Usuario:
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if usuario.estado_solicitud != "pendiente":
        raise HTTPException(status_code=409, detail="Esta cuenta no tiene una solicitud pendiente.")
    return usuario


@router.post("/{usuario_id}/aprobar", response_model=UsuarioAdminOut)
def aprobar_solicitud(
    usuario_id: UUID,
    payload: Aprobacion,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario_actual=Depends(requiere("gestionar_usuarios")),
):
    """El jefe de laboratorio revisa la solicitud, confirma el rol y la habilita."""
    usuario = _solicitud(db, usuario_id)
    usuario.rol = payload.rol
    usuario.especialidad = _especialidad_segun_rol(payload.rol, payload.especialidad or usuario.especialidad)
    usuario.activo = True
    usuario.estado_solicitud = None
    db.commit()
    db.refresh(usuario)
    background_tasks.add_task(
        enviar_correo,
        [usuario.email],
        "[CustodiaDigital] Tu cuenta fue aprobada",
        f"Hola {usuario.nombre}:\n\nEl jefe de laboratorio aprobó tu cuenta como "
        f"{ETIQUETAS_ROL.get(usuario.rol, usuario.rol.value)}. Ya puedes iniciar sesión en CustodiaDigital.",
    )
    return _a_salida(usuario, 0)


@router.post("/{usuario_id}/rechazar", response_model=UsuarioAdminOut)
def rechazar_solicitud(
    usuario_id: UUID,
    payload: Rechazo,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario_actual=Depends(requiere("gestionar_usuarios")),
):
    """La solicitud rechazada no se borra: queda registrada, sin acceso."""
    usuario = _solicitud(db, usuario_id)
    usuario.activo = False
    usuario.estado_solicitud = "rechazada"
    db.commit()
    db.refresh(usuario)
    motivo = (payload.motivo or "").strip()
    background_tasks.add_task(
        enviar_correo,
        [usuario.email],
        "[CustodiaDigital] Tu solicitud de cuenta fue rechazada",
        f"Hola {usuario.nombre}:\n\nEl jefe de laboratorio rechazó tu solicitud de cuenta."
        + (f"\n\nMotivo: {motivo}" if motivo else "")
        + "\n\nSi crees que es un error, comunícate con el laboratorio.",
    )
    return _a_salida(usuario, 0)


# Sprint 6 (historia 27): el jefe de laboratorio levanta un bloqueo por intentos fallidos.
@router.post("/{usuario_id}/desbloquear", response_model=UsuarioAdminOut)
def desbloquear_usuario(
    usuario_id: UUID,
    db: Session = Depends(get_db),
    usuario_actual=Depends(requiere("gestionar_usuarios")),
):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    usuario.bloqueado_hasta = None
    usuario.intentos_fallidos = 0
    db.commit()
    db.refresh(usuario)
    print(f"[seguridad] {usuario_actual.email} desbloqueó la cuenta {usuario.email}", flush=True)
    return _a_salida(usuario, 0)


# Sprint 6 (historia 24): si alguien pierde el celular, el jefe de laboratorio le reinicia
# el 2FA; en su próximo ingreso tendrá que escanear un QR nuevo.
@router.post("/{usuario_id}/reiniciar-2fa", response_model=UsuarioAdminOut)
def reiniciar_2fa(
    usuario_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario_actual=Depends(requiere("gestionar_usuarios")),
):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if usuario.id == usuario_actual.id:
        raise HTTPException(
            status_code=400,
            detail="No puedes reiniciar tu propia verificación en dos pasos: pídeselo a otro jefe de laboratorio.",
        )
    usuario.totp_secreto = None
    usuario.totp_activo = False
    usuario.totp_ultimo_paso = None
    usuario.sesion_version = (usuario.sesion_version or 0) + 1  # cierra sus sesiones abiertas
    db.commit()
    db.refresh(usuario)
    print(f"[seguridad] {usuario_actual.email} reinició la verificación en dos pasos de {usuario.email}", flush=True)
    background_tasks.add_task(
        enviar_correo,
        [usuario.email],
        "[CustodiaDigital] Se reinició tu verificación en dos pasos",
        f"Hola {usuario.nombre}:\n\n{usuario_actual.nombre} (jefe de laboratorio) reinició tu verificación "
        "en dos pasos. En tu próximo ingreso tendrás que escanear un código QR nuevo.\n\n"
        "Si no lo pediste, avísale de inmediato.",
    )
    return _a_salida(usuario, 0)