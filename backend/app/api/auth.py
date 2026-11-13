import threading
from datetime import datetime, timedelta, timezone
from math import ceil
from zoneinfo import ZoneInfo
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.db.session import get_db
from app.schemas.usuario import UsuarioCreate, UsuarioOut, LoginRequest, TokenResponse, RefreshRequest
from app.models.usuario import Usuario, RolEnum
from app.services.correo_service import enviar_correo
from app.core.security import hash_password, verify_password, validar_password, crear_access_token, crear_refresh_token, get_current_user
from app.core.config import settings
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter(prefix="/auth", tags=["auth"])

def _avisar_solicitud(nombre: str, email: str, rol: str, especialidad: str, institucion: str, correos_admin: list) -> None:
    enviar_correo(
        correos_admin,
        f"[CustodiaDigital] Nueva solicitud de cuenta: {nombre}",
        f"{nombre} ({email}) pidió una cuenta de {rol}.\n"
        f"Especialidad: {especialidad}\n"
        f"Institución:  {institucion or '—'}\n\n"
        "Revísala en CustodiaDigital > Usuarios y roles > Solicitudes pendientes.",
    )


def _verificar_estado_cuenta(usuario: Usuario) -> None:
    """Sprint 6 (historia 25): una cuenta pedida desde "Solicitar acceso" no entra
    hasta que el jefe de laboratorio la aprueba."""
    if usuario.estado_solicitud == "pendiente":
        raise HTTPException(
            status_code=403,
            detail="Tu solicitud de cuenta está pendiente de aprobación por el jefe de laboratorio.",
        )
    if usuario.estado_solicitud == "rechazada":
        raise HTTPException(status_code=403, detail="Tu solicitud de cuenta fue rechazada por el jefe de laboratorio.")
    if not usuario.activo:  # Sprint 5 (historia 19.1)
        raise HTTPException(status_code=403, detail="Tu usuario está desactivado. Contacta al jefe de laboratorio.")



# ---------------------------------------------------------------------------
# Sprint 6 (historia 27): bloqueo temporal tras varios intentos fallidos.

def _comprobar_bloqueo(usuario) -> None:
    if usuario and usuario.bloqueado_hasta and usuario.bloqueado_hasta > datetime.now(timezone.utc):
        minutos = ceil((usuario.bloqueado_hasta - datetime.now(timezone.utc)).total_seconds() / 60)
        raise HTTPException(
            status_code=429,
            detail=f"Cuenta bloqueada temporalmente por {settings.MAX_INTENTOS_LOGIN} intentos fallidos. "
                   f"Intenta de nuevo en {minutos} minuto(s) o pide al jefe de laboratorio que la desbloquee.",
        )


def _registrar_fallo(db: Session, usuario: Usuario) -> None:
    usuario.intentos_fallidos = (usuario.intentos_fallidos or 0) + 1
    if usuario.intentos_fallidos >= settings.MAX_INTENTOS_LOGIN:
        usuario.bloqueado_hasta = datetime.now(timezone.utc) + timedelta(minutes=settings.BLOQUEO_LOGIN_MIN)
        usuario.intentos_fallidos = 0
        hasta = usuario.bloqueado_hasta.astimezone(ZoneInfo("America/Lima")).strftime("%d/%m/%Y %H:%M")
        print(f"[seguridad] Cuenta {usuario.email} bloqueada hasta {hasta} por intentos fallidos", flush=True)
        admins = [u.email for u in db.query(Usuario).filter(Usuario.rol == RolEnum.admin, Usuario.activo.is_(True)).all()]
        # El correo va en un hilo aparte: la respuesta de error no espera al servidor de correo.
        threading.Thread(
            target=enviar_correo,
            args=(
                sorted(set(admins + [usuario.email])),
                "[CustodiaDigital] Cuenta bloqueada por intentos fallidos",
                f"La cuenta de {usuario.nombre} ({usuario.email}) se bloqueó tras "
                f"{settings.MAX_INTENTOS_LOGIN} intentos fallidos de inicio de sesión.\n"
                f"Queda bloqueada hasta las {hasta} (hora de Lima).\n\n"
                "Si no fuiste tú, avisa al jefe de laboratorio.",
            ),
            daemon=True,
        ).start()
    db.commit()


def _autenticar(db: Session, usuario, password: str, recordarme: bool) -> TokenResponse:
    """Login común para la página y para Swagger (/token)."""
    _comprobar_bloqueo(usuario)
    if not usuario or not verify_password(password, usuario.password_hash):
        if usuario:
            _registrar_fallo(db, usuario)
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos.")
    _verificar_estado_cuenta(usuario)
    if usuario.intentos_fallidos or usuario.bloqueado_hasta:
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        db.commit()
    return TokenResponse(
        access_token=crear_access_token(str(usuario.id)),
        refresh_token=crear_refresh_token(str(usuario.id), recordarme),
    )
@router.post("/registro", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def registro(payload: UsuarioCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Sprint 6 (historia 25): cualquiera puede SOLICITAR una cuenta de perito, pero
    queda inactiva y pendiente hasta que el jefe de laboratorio la apruebe."""
    existe = db.query(Usuario).filter(Usuario.email == payload.email).first()
    if existe:
        raise HTTPException(status_code=409, detail="El email ya está registrado.")
    validar_password(payload.password)  # Sprint 6 (historia 27)
    if not (payload.institucion or "").strip():
        raise HTTPException(status_code=400, detail="Indica tu institución (si eres perito particular, escríbelo así).")
    if not (payload.registro_profesional or "").strip():
        raise HTTPException(status_code=400, detail="Indica tu N° de registro o colegiatura.")
    if not payload.nombre.strip():
        raise HTTPException(status_code=400, detail="Escribe tu nombre completo.")

    nuevo = Usuario(
        nombre=payload.nombre.strip(),
        email=payload.email,
        password_hash=hash_password(payload.password),
        especialidad=payload.especialidad,
        rol=RolEnum(payload.rol),
        institucion=(payload.institucion or "").strip() or None,
        registro_profesional=(payload.registro_profesional or "").strip() or None,
        telefono=(payload.telefono or "").strip() or None,
        activo=False,
        estado_solicitud="pendiente",
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    admins = [u.email for u in db.query(Usuario).filter(Usuario.rol == RolEnum.admin, Usuario.activo.is_(True)).all()]
    if settings.ALERTAS_EMAIL_ADMIN:
        admins.append(settings.ALERTAS_EMAIL_ADMIN)
    etiqueta_rol = "perito de parte" if payload.rol == "perito_parte" else "perito oficial"
    background_tasks.add_task(
        _avisar_solicitud, nuevo.nombre, nuevo.email, etiqueta_rol, payload.especialidad.value, nuevo.institucion, admins
    )
    return nuevo

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == payload.email).first()
    return _autenticar(db, usuario, payload.password, payload.recordarme)

@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        data = jwt.decode(payload.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if data.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Token inválido.")
        usuario_id = data.get("sub")
        recordarme = bool(data.get("rec"))
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado.")

    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario or not usuario.activo:
        raise HTTPException(status_code=401, detail="Usuario no encontrado o desactivado.")

    # Sprint 6 (historia 25): el refresh conserva si la sesión es persistente.
    return TokenResponse(
        access_token=crear_access_token(str(usuario.id)),
        refresh_token=crear_refresh_token(str(usuario.id), recordarme),
    )
@router.post("/token", response_model=TokenResponse)
def login_swagger(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    usuario = db.query(Usuario).filter(Usuario.email == form.username).first()
    return _autenticar(db, usuario, form.password, False)

@router.get("/me", response_model=UsuarioOut)
def me(usuario_actual=Depends(get_current_user)):
    return usuario_actual