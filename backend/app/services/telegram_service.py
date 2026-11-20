"""Sprint 7 (historia 33): alertas también por Telegram.

Envía un mensaje corto al grupo del laboratorio con un bot de Telegram.
- Sin TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID, no hace nada (y no falla).
- Lo que se envía SALE del laboratorio: por eso los mensajes llevan solo lo mínimo
  (tipo de aviso, número de caso, fecha). Nunca nombres de archivo, hashes ni personas.
- Un fallo de Telegram nunca debe tumbar una alerta ni un recordatorio.
"""
import json
import urllib.request

from app.core.config import settings

API = "https://api.telegram.org/bot{token}/{metodo}"


def telegram_activo() -> bool:
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)


def _llamar(metodo: str, datos: dict = None) -> dict:
    url = API.format(token=settings.TELEGRAM_BOT_TOKEN, metodo=metodo)
    cuerpo = json.dumps(datos or {}).encode("utf-8")
    peticion = urllib.request.Request(url, data=cuerpo, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(peticion, timeout=10) as respuesta:
        return json.loads(respuesta.read().decode("utf-8"))


def enviar_telegram(texto: str) -> bool:
    """Devuelve True si Telegram aceptó el mensaje."""
    if not telegram_activo():
        return False
    try:
        r = _llamar("sendMessage", {
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": texto,
            "disable_web_page_preview": True,
        })
        return bool(r.get("ok"))
    except Exception as e:
        # Nunca imprimir la URL: lleva el token.
        print(f"[telegram] No se pudo enviar el mensaje: {type(e).__name__}", flush=True)
        return False


def chats_recientes() -> list:
    """Chats donde el bot recibió algo hace poco (para averiguar TELEGRAM_CHAT_ID)."""
    r = _llamar("getUpdates")
    chats = {}
    for u in r.get("result", []):
        for clave in ("message", "my_chat_member", "channel_post"):
            chat = (u.get(clave) or {}).get("chat")
            if chat:
                chats[chat["id"]] = chat.get("title") or chat.get("username") or chat.get("first_name")
    return [{"id": k, "nombre": v} for k, v in chats.items()]