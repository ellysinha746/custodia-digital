"""Sprint 7 (historia 33): muestra los chats donde está el bot, para llenar TELEGRAM_CHAT_ID.
Uso: docker compose exec api python -m app.scripts.telegram_chat_id"""
from app.core.config import settings
from app.services.telegram_service import chats_recientes

if not settings.TELEGRAM_BOT_TOKEN:
    print("Falta TELEGRAM_BOT_TOKEN en backend/.env")
else:
    chats = chats_recientes()
    if not chats:
        print("No hay mensajes recientes. Escribe /start en el grupo y vuelve a correr esto.")
    for c in chats:
        print(f"{c['id']}\t{c['nombre']}")