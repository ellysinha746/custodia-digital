"""Sprint 6 (historia 27): clave propia para los sellos HMAC de reportes y actas.

Antes los sellos se firmaban con SECRET_KEY, la misma clave de los tokens de sesión: si
se rotaba (por ejemplo, para cerrar todas las sesiones), todos los reportes y actas
emitidos dejaban de verificar. Ahora se firman con SELLO_SECRET_KEY y, al verificar,
se acepta también SECRET_KEY para lo emitido antes de este cambio.
"""
import hashlib
import hmac

from app.core.config import settings


def _clave_firma() -> bytes:
    return (settings.SELLO_SECRET_KEY or settings.SECRET_KEY).encode("utf-8")


def _claves_verificacion() -> list:
    claves = [settings.SELLO_SECRET_KEY, settings.SECRET_KEY]
    return [c.encode("utf-8") for c in dict.fromkeys(claves) if c]


def firmar(mensaje: bytes) -> str:
    return hmac.new(_clave_firma(), mensaje, hashlib.sha256).hexdigest()


def firma_valida(mensaje: bytes, firma: str) -> bool:
    return any(
        hmac.compare_digest(hmac.new(clave, mensaje, hashlib.sha256).hexdigest(), firma or "")
        for clave in _claves_verificacion()
    )
