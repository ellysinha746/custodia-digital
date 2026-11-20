from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.permisos import requiere
from app.services.telegram_service import enviar_telegram, telegram_activo

# Sprint 7 (historia 33): estado del bot de Telegram y mensaje de prueba.
router = APIRouter(prefix="/telegram", tags=["telegram"])


class EstadoTelegram(BaseModel):
    activo: bool


class EnvioTelegram(BaseModel):
    enviado: bool


@router.get("/estado", response_model=EstadoTelegram)
def estado(usuario_actual=Depends(requiere("ver_dashboard"))):
    return EstadoTelegram(activo=telegram_activo())


@router.post("/prueba", response_model=EnvioTelegram)
def prueba(usuario_actual=Depends(requiere("ver_dashboard"))):
    enviado = enviar_telegram(
        f"✅ Mensaje de prueba de CustodiaDigital\nEnviado por: {usuario_actual.nombre}"
    )
    return EnvioTelegram(enviado=enviado)