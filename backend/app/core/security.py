from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.usuario import Usuario
from app.core.totp import necesita_2fa  # Sprint 6 (historia 24)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# Sprint 6 (historia 27): política de contraseñas.
MIN_LARGO_PASSWORD = 10


def validar_password(password: str) -> None:
    """Exige mínimo 10 caracteres, con al menos una letra y un número."""
    if len(password) < MIN_LARGO_PASSWORD:
        raise HTTPException(
            status_code=400,
            detail=f"La contraseña debe tener al menos {MIN_LARGO_PASSWORD} caracteres.",
        )
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise HTTPException(status_code=400, detail="La contraseña debe combinar letras y números.")

def crear_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    to_encode.update({"exp": datetime.utcnow() + expires_delta})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

# Sprint 6 (historia 24): "mfa" marca que la sesión se abrió con el código de 2FA.
# "ver" es la sesion_version del usuario: si cambió, el token ya no vale.
def crear_access_token(usuario_id: str, mfa: bool = False, ver: int = 0) -> str:
    return crear_token(
        {"sub": usuario_id, "type": "access", "mfa": mfa, "ver": ver},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

def crear_refresh_token(usuario_id: str, recordarme: bool = False, mfa: bool = False, ver: int = 0) -> str:
    """Sprint 6 (historia 25): con "Recordarme" la sesión dura REFRESH_TOKEN_EXPIRE_DAYS
    días; sin marcarlo, solo REFRESH_SIN_RECORDAR_HORAS horas."""
    duracion = (
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        if recordarme
        else timedelta(hours=settings.REFRESH_SIN_RECORDAR_HORAS)
    )
    return crear_token({"sub": usuario_id, "type": "refresh", "rec": recordarme, "mfa": mfa, "ver": ver}, duracion)


def sesion_vigente(usuario: Usuario, payload: dict) -> bool:
    """Sprint 6 (historia 24): el token es de la versión de sesión actual del usuario."""
    return payload.get("ver", 0) == (usuario.sesion_version or 0)

def crear_token_2fa(usuario_id: str, recordarme: bool) -> str:
    """Sprint 6 (historia 24): pase temporal entre la contraseña y el código.
    No sirve para usar la API, solo para los endpoints /auth/2fa/*."""
    return crear_token(
        {"sub": usuario_id, "type": "2fa", "rec": recordarme},
        timedelta(minutes=settings.TOKEN_2FA_MIN),
    )

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "access":
            raise credentials_exception
        usuario_id = payload.get("sub")
        if usuario_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if usuario is None:
        raise credentials_exception
    if not usuario.activo:  # Sprint 5 (historia 19.1)
        raise HTTPException(status_code=403, detail="Tu usuario está desactivado. Contacta al jefe de laboratorio.")
    # Sprint 6 (historia 24): una sesión abierta sin código (p. ej. antes de exigir 2FA) ya no vale,
    # ni una sesión anterior a un reinicio del 2FA.
    if necesita_2fa(usuario) and not payload.get("mfa"):
        raise HTTPException(
            status_code=401,
            detail="Tu cuenta requiere verificación en dos pasos. Vuelve a iniciar sesión.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not sesion_vigente(usuario, payload):
        raise HTTPException(
            status_code=401,
            detail="Tu sesión se cerró por seguridad. Vuelve a iniciar sesión.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return usuario