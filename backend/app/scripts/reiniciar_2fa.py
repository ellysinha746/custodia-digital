"""Sprint 6 (historia 24): reinicia la verificación en dos pasos de un usuario desde el servidor.

Es el rescate para cuando el ÚNICO jefe de laboratorio pierde el celular (desde la página
nadie puede reiniciarse su propio 2FA). Solo lo puede correr quien tiene acceso al servidor.

Uso (con docker):
    docker compose exec api python -m app.scripts.reiniciar_2fa correo@example.com
"""
import sys

from app.db.session import SessionLocal
from app.models.usuario import Usuario
import app.main  # noqa: F401  (carga todos los modelos)


def main() -> None:
    if len(sys.argv) != 2:
        print("Uso: python -m app.scripts.reiniciar_2fa correo@example.com")
        sys.exit(1)
    email = sys.argv[1].strip()
    db = SessionLocal()
    try:
        usuario = db.query(Usuario).filter(Usuario.email == email).first()
        if not usuario:
            print(f"No existe un usuario con el correo {email}.")
            sys.exit(1)
        usuario.totp_secreto = None
        usuario.totp_activo = False
        usuario.totp_ultimo_paso = None
        usuario.sesion_version = (usuario.sesion_version or 0) + 1  # cierra sus sesiones abiertas
        db.commit()
        print(f"[seguridad] Se reinició la verificación en dos pasos de {email} desde el servidor.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
