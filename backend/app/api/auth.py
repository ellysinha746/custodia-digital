import threading
from datetime import datetime, timedelta, timezone
from math import ceil
from zoneinfo import ZoneInfo
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.db.session import get_db
from app.schemas.usuario import (
    UsuarioCreate, UsuarioOut, LoginRequest, TokenResponse, RefreshRequest,
    Token2FA, Codigo2FA, Configuracion2FA,
)
from app.models.usuario import Usuario, RolEnum
from app.services.correo_service import enviar_correo
from app.core.security import (
    hash_password, verify_password, validar_password, crear_access_token, crear_refresh_token,
    crear_token_2fa, get_current_user, sesion_vigente,
)
from app.core import totp  # Sprint 6 (historia 24)
from app.core.totp import necesita_2fa
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


def _emitir_sesion(db: Session, usuario: Usuario, recordarme: bool, mfa: bool = False) -> TokenResponse:
    """Login completo: limpia los intentos fallidos y entrega los tokens de sesión."""
    if usuario.intentos_fallidos or usuario.bloqueado_hasta:
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
    db.commit()
    ver = usuario.sesion_version or 0
    return TokenResponse(
        access_token=crear_access_token(str(usuario.id), mfa, ver),
        refresh_token=crear_refresh_token(str(usuario.id), recordarme, mfa, ver),
    )


def _autenticar(db: Session, usuario, password: str, recordarme: bool) -> TokenResponse:
    """Login común para la página y para Swagger (/token)."""
    _comprobar_bloqueo(usuario)
    if not usuario or not verify_password(password, usuario.password_hash):
        if usuario:
            _registrar_fallo(db, usuario)
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos.")
    _verificar_estado_cuenta(usuario)
    # Sprint 6 (historia 24): con 2FA, la contraseña sola no abre sesión. Los intentos
    # fallidos NO se limpian aquí: así no se puede adivinar el código alternando con la clave.
    if necesita_2fa(usuario):
        return TokenResponse(
            requiere_2fa=True,
            configurar_2fa=not usuario.totp_activo,
            token_2fa=crear_token_2fa(str(usuario.id), recordarme),
        )
    return _emitir_sesion(db, usuario, recordarme)


# ---------------------------------------------------------------------------
# Sprint 6 (historia 24): verificación en dos pasos (TOTP).

def _usuario_de_token_2fa(db: Session, token: str):
    expirado = HTTPException(
        status_code=401, detail="La verificación expiró. Vuelve a ingresar tu correo y contraseña."
    )
    try:
        data = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise expirado
    if data.get("type") != "2fa":
        raise expirado
    # with_for_update: bloquea la fila hasta el commit, así las peticiones simultáneas
    # se atienden una por una (no se pierden intentos fallidos ni se repite un código).
    usuario = db.query(Usuario).filter(Usuario.id == data.get("sub")).with_for_update().first()
    if not usuario:
        raise expirado
    _comprobar_bloqueo(usuario)
    _verificar_estado_cuenta(usuario)
    return usuario, bool(data.get("rec"))


def _codigo_incorrecto(db: Session, usuario: Usuario) -> None:
    _registrar_fallo(db, usuario)  # cuenta para el bloqueo de la historia 27
    _comprobar_bloqueo(usuario)    # si con este fallo se bloqueó, avisa del bloqueo
    raise HTTPException(
        status_code=401,
        detail="Código incorrecto o ya usado. Revisa que la hora de tu celular sea la correcta.",
    )


def _avisar_2fa(usuario: Usuario, asunto: str, texto: str) -> None:
    threading.Thread(
        target=enviar_correo,
        args=([usuario.email], f"[CustodiaDigital] {asunto}", texto),
        daemon=True,
    ).start()


@router.post("/2fa/configurar", response_model=Configuracion2FA)
def configurar_2fa(payload: Token2FA, db: Session = Depends(get_db)):
    """Primer ingreso con 2FA: genera el secreto y su QR para la app autenticadora.
    Si el usuario ya tiene 2FA activo no se puede volver a configurar desde aquí
    (si no, bastaría la contraseña para cambiarlo): debe reiniciarlo el jefe de laboratorio."""
    usuario, _ = _usuario_de_token_2fa(db, payload.token_2fa)
    if usuario.totp_activo:
        raise HTTPException(
            status_code=409,
            detail="Ya tienes la verificación en dos pasos activa. Si perdiste el celular, "
                   "pide al jefe de laboratorio que la reinicie.",
        )
    secreto = totp.nuevo_secreto(usuario)
    db.commit()
    uri = totp.uri_aprovisionamiento(usuario, secreto)
    return Configuracion2FA(secreto=secreto, uri=uri, qr=totp.qr_data_uri(uri))


@router.post("/2fa/activar", response_model=TokenResponse)
def activar_2fa(payload: Codigo2FA, db: Session = Depends(get_db)):
    """Confirma el primer código de la app: activa el 2FA y abre la sesión."""
    usuario, recordarme = _usuario_de_token_2fa(db, payload.token_2fa)
    if usuario.totp_activo:
        raise HTTPException(status_code=409, detail="La verificación en dos pasos ya está activa.")
    if not usuario.totp_secreto:
        raise HTTPException(status_code=400, detail="Primero genera el código QR.")
    if not totp.verificar_codigo(usuario, payload.codigo):
        _codigo_incorrecto(db, usuario)
    usuario.totp_activo = True
    print(f"[seguridad] {usuario.email} activó la verificación en dos pasos", flush=True)
    _avisar_2fa(
        usuario,
        "Verificación en dos pasos activada",
        f"Hola {usuario.nombre}:\n\nSe activó la verificación en dos pasos en tu cuenta. "
        "Desde ahora, al iniciar sesión se te pedirá el código de tu app autenticadora.\n\n"
        "Si no fuiste tú, avisa de inmediato al jefe de laboratorio.",
    )
    return _emitir_sesion(db, usuario, recordarme, mfa=True)


@router.post("/2fa/verificar", response_model=TokenResponse)
def verificar_2fa(payload: Codigo2FA, db: Session = Depends(get_db)):
    """Segundo paso del login: el código de 6 dígitos de la app autenticadora."""
    usuario, recordarme = _usuario_de_token_2fa(db, payload.token_2fa)
    if not usuario.totp_activo:
        raise HTTPException(status_code=400, detail="Primero configura la verificación en dos pasos.")
    if not totp.verificar_codigo(usuario, payload.codigo):
        _codigo_incorrecto(db, usuario)
    return _emitir_sesion(db, usuario, recordarme, mfa=True)
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
    # Sprint 6 (historia 24): fila bloqueada para que el conteo de intentos no se pierda en paralelo.
    usuario = db.query(Usuario).filter(Usuario.email == payload.email).with_for_update().first()
    return _autenticar(db, usuario, payload.password, payload.recordarme)

@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        data = jwt.decode(payload.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if data.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Token inválido.")
        usuario_id = data.get("sub")
        recordarme = bool(data.get("rec"))
        mfa = bool(data.get("mfa"))
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado.")

    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario or not usuario.activo:
        raise HTTPException(status_code=401, detail="Usuario no encontrado o desactivado.")
    # Sprint 6 (historia 24): una sesión sin código no se renueva si la cuenta exige 2FA.
    if necesita_2fa(usuario) and not mfa:
        raise HTTPException(status_code=401, detail="Tu cuenta requiere verificación en dos pasos. Vuelve a iniciar sesión.")
    if not sesion_vigente(usuario, data):
        raise HTTPException(status_code=401, detail="Tu sesión se cerró por seguridad. Vuelve a iniciar sesión.")

    # Sprint 6 (historia 25): el refresh conserva si la sesión es persistente.
    ver = usuario.sesion_version or 0
    return TokenResponse(
        access_token=crear_access_token(str(usuario.id), mfa, ver),
        refresh_token=crear_refresh_token(str(usuario.id), recordarme, mfa, ver),
    )
@router.post("/token", response_model=TokenResponse)
def login_swagger(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    usuario = db.query(Usuario).filter(Usuario.email == form.username).with_for_update().first()
    respuesta = _autenticar(db, usuario, form.password, False)
    if respuesta.requiere_2fa:  # Sprint 6 (historia 24)
        raise HTTPException(
            status_code=401,
            detail="Esta cuenta usa verificación en dos pasos: inicia sesión desde la página web.",
        )
    return respuesta

@router.get("/me", response_model=UsuarioOut)
def me(usuario_actual=Depends(get_current_user)):
    return usuario_actual