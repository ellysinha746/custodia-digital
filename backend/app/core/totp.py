"""Sprint 6 (historia 24): verificación en dos pasos con TOTP (RFC 6238).

- El secreto de cada usuario se guarda CIFRADO (Fernet, clave derivada de SECRET_KEY):
  si alguien copia la base de datos, no puede generar los códigos.
- Un código ya usado no se acepta otra vez (se recuerda el último "paso" de 30 s).
- Se toleran ±30 s de desfase entre el reloj del celular y el del servidor.
"""
import base64
import hashlib
import hmac
import io
from datetime import datetime, timezone

import pyotp
import qrcode
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _fernet() -> Fernet:
    clave = hashlib.sha256(b"custodia-totp:" + settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(clave))


def es_obligatorio(usuario) -> bool:
    roles = {r.strip() for r in settings.TOTP_ROLES_OBLIGATORIO.split(",") if r.strip()}
    rol = getattr(usuario.rol, "value", usuario.rol)
    return rol in roles


def necesita_2fa(usuario) -> bool:
    """El usuario no recibe sesión sin el código: lo tiene activado o su rol lo exige."""
    return bool(usuario.totp_activo) or es_obligatorio(usuario)


def nuevo_secreto(usuario) -> str:
    """Genera un secreto nuevo (todavía sin activar) y lo deja cifrado en el usuario."""
    secreto = pyotp.random_base32()
    usuario.totp_secreto = _fernet().encrypt(secreto.encode()).decode()
    usuario.totp_ultimo_paso = None
    return secreto


def _secreto(usuario):
    if not usuario.totp_secreto:
        return None
    try:
        return _fernet().decrypt(usuario.totp_secreto.encode()).decode()
    except InvalidToken:
        # Cambió SECRET_KEY: el secreto ya no se puede leer; el jefe debe reiniciar el 2FA.
        return None


def uri_aprovisionamiento(usuario, secreto: str) -> str:
    return pyotp.TOTP(secreto).provisioning_uri(name=usuario.email, issuer_name=settings.TOTP_EMISOR)


def qr_data_uri(texto: str) -> str:
    imagen = qrcode.make(texto, box_size=6, border=2)
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def codigo_correo(usuario) -> str:
    """Código de 6 dígitos que se manda al CORREO al configurar el 2FA: así, para registrar
    un celular no basta la contraseña, también hace falta acceso al correo del usuario.
    Sale del secreto pendiente (que se cifra con un IV aleatorio), así que cada QR nuevo
    invalida el código anterior y no hace falta guardarlo en la base."""
    mensaje = f"enrolamiento:{usuario.id}:{usuario.totp_secreto}".encode()
    digest = hmac.new(settings.SECRET_KEY.encode(), mensaje, hashlib.sha256).digest()
    return f"{int.from_bytes(digest[:8], 'big') % 1_000_000:06d}"


def verificar_codigo_correo(usuario, codigo: str) -> bool:
    codigo = (codigo or "").replace(" ", "").strip()
    return bool(usuario.totp_secreto) and hmac.compare_digest(codigo_correo(usuario), codigo)


def enmascarar_correo(email: str) -> str:
    """fiscal.quispe@example.com → fi***@example.com"""
    nombre, _, dominio = email.partition("@")
    return f"{nombre[:2]}***@{dominio}"


def verificar_codigo(usuario, codigo: str) -> bool:
    """True si el código es válido y no se usó antes. Si es válido, recuerda su paso."""
    secreto = _secreto(usuario)
    codigo = (codigo or "").replace(" ", "").strip()
    if not secreto or len(codigo) != 6 or not codigo.isdigit():
        return False
    totp = pyotp.TOTP(secreto)
    ahora = totp.timecode(datetime.now(timezone.utc))
    for paso in (ahora - 1, ahora, ahora + 1):
        if hmac.compare_digest(totp.generate_otp(paso), codigo):
            if usuario.totp_ultimo_paso is not None and paso <= usuario.totp_ultimo_paso:
                return False  # código repetido
            usuario.totp_ultimo_paso = paso
            return True
    return False
