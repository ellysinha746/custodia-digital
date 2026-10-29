from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.db.session import get_db
from app.schemas.usuario import UsuarioCreate, UsuarioOut, LoginRequest, TokenResponse, RefreshRequest
from app.models.usuario import Usuario
from app.core.security import hash_password, verify_password, crear_access_token, crear_refresh_token, get_current_user
from app.core.config import settings
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/registro", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def registro(payload: UsuarioCreate, db: Session = Depends(get_db)):
    existe = db.query(Usuario).filter(Usuario.email == payload.email).first()
    if existe:
        raise HTTPException(status_code=409, detail="El email ya está registrado.")

    nuevo = Usuario(
        nombre=payload.nombre,
        email=payload.email,
        password_hash=hash_password(payload.password),
        especialidad=payload.especialidad,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == payload.email).first()
    if not usuario or not verify_password(payload.password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos.")

    return TokenResponse(
        access_token=crear_access_token(str(usuario.id)),
        refresh_token=crear_refresh_token(str(usuario.id)),
    )

@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        data = jwt.decode(payload.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if data.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Token inválido.")
        usuario_id = data.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado.")

    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuario no encontrado.")

    return TokenResponse(
        access_token=crear_access_token(str(usuario.id)),
        refresh_token=crear_refresh_token(str(usuario.id)),
    )
@router.post("/token", response_model=TokenResponse)
def login_swagger(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    usuario = db.query(Usuario).filter(Usuario.email == form.username).first()
    if not usuario or not verify_password(form.password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos.")

    return TokenResponse(
        access_token=crear_access_token(str(usuario.id)),
        refresh_token=crear_refresh_token(str(usuario.id)),
    )

@router.get("/me", response_model=UsuarioOut)
def me(usuario_actual=Depends(get_current_user)):
    return usuario_actual