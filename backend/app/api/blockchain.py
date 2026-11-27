"""Sprint 8 (historia 39): anclaje del historial de custodia en Bitcoin (OpenTimestamps)."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.permisos import exigir
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.anclaje_blockchain import AnclajeBlockchain
from app.services import blockchain_service

router = APIRouter(prefix="/blockchain", tags=["blockchain"])


class AnclajeOut(BaseModel):
    id: UUID
    creado_en: datetime
    creado_por: Optional[str]
    hasta: datetime
    total_registros: int
    huella: str
    calendarios: List[str]
    estado: str
    bloque_bitcoin: Optional[int]
    actualizado_en: Optional[datetime]


def _salida(a: AnclajeBlockchain) -> AnclajeOut:
    return AnclajeOut(
        id=a.id, creado_en=a.creado_en, creado_por=a.creado_por.nombre if a.creado_por else None,
        hasta=a.hasta, total_registros=a.total_registros, huella=a.huella, calendarios=a.calendarios,
        estado=a.estado, bloque_bitcoin=a.bloque_bitcoin, actualizado_en=a.actualizado_en,
    )


def _obtener(db: Session, anclaje_id: UUID) -> AnclajeBlockchain:
    a = db.get(AnclajeBlockchain, anclaje_id)
    if not a:
        raise HTTPException(status_code=404, detail="Anclaje no encontrado.")
    return a


def _nombre(a: AnclajeBlockchain, extension: str) -> str:
    return f"historial_custodia_{a.hasta.strftime('%Y%m%d_%H%M%S')}.{extension}"


@router.get("/anclajes", response_model=List[AnclajeOut])
def listar(db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    exigir(usuario_actual, "ver_blockchain")
    filas = db.query(AnclajeBlockchain).order_by(AnclajeBlockchain.hasta.desc()).limit(50).all()
    return [_salida(a) for a in filas]


@router.post("/anclajes", response_model=AnclajeOut, status_code=201)
def anclar_ahora(db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    """Ancla ya mismo el historial de custodia completo hasta este momento."""
    exigir(usuario_actual, "anclar_blockchain")
    try:
        return _salida(blockchain_service.anclar(db, usuario_actual.id))
    except blockchain_service.SinCalendarios as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/anclajes/{anclaje_id}/actualizar", response_model=AnclajeOut)
def actualizar(anclaje_id: UUID, db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    """Consulta si Bitcoin ya confirmó el anclaje (suele tardar unas horas)."""
    exigir(usuario_actual, "anclar_blockchain")
    return _salida(blockchain_service.actualizar(db, _obtener(db, anclaje_id)))


@router.get("/anclajes/{anclaje_id}/verificar")
def verificar(anclaje_id: UUID, db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    exigir(usuario_actual, "ver_blockchain")
    return blockchain_service.verificar(db, _obtener(db, anclaje_id))


@router.get("/anclajes/{anclaje_id}/ots")
def descargar_prueba(anclaje_id: UUID, db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    """La prueba .ots, para verificar por cuenta propia en opentimestamps.org."""
    exigir(usuario_actual, "ver_blockchain")
    a = _obtener(db, anclaje_id)
    return Response(
        content=a.prueba_ots, media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{_nombre(a, "txt.ots")}"'},
    )


@router.get("/anclajes/{anclaje_id}/historial")
def descargar_historial(anclaje_id: UUID, db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    """El historial tal como está HOY en la base, hasta la fecha del anclaje. Junto con el .ots,
    opentimestamps.org confirma si es el mismo que se ancló. Contiene datos de la custodia:
    solo para el jefe de laboratorio."""
    exigir(usuario_actual, "anclar_blockchain")
    a = _obtener(db, anclaje_id)
    texto, _ = blockchain_service.historial_canonico(db, a.hasta)
    return Response(
        content=texto, media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_nombre(a, "txt")}"'},
    )
