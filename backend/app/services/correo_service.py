import smtplib
from email.message import EmailMessage
from typing import Iterable

from app.core.config import settings


def enviar_correo(destinatarios: Iterable[str], asunto: str, cuerpo: str) -> bool:
    """Envía un correo de texto plano. Si SMTP_HOST está vacío, lo imprime en
    la consola del backend (modo desarrollo) para poder demostrarlo sin SMTP."""
    destinatarios = sorted({d for d in destinatarios if d})
    if not destinatarios:
        return False

    if not settings.SMTP_HOST:
        print("\n========== [CORREO - modo consola, SMTP_HOST vacío] ==========")
        print(f"Para:   {', '.join(destinatarios)}")
        print(f"Asunto: {asunto}\n")
        print(cuerpo)
        print("===============================================================\n", flush=True)
        return True

    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = ", ".join(destinatarios)
    msg.set_content(cuerpo)

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as servidor:
            if settings.SMTP_TLS:
                servidor.starttls()
            if settings.SMTP_USER:
                servidor.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            servidor.send_message(msg)
        return True
    except Exception as e:  # un correo fallido nunca debe tumbar la verificación
        print(f"[correo] No se pudo enviar '{asunto}': {e}", flush=True)
        return False