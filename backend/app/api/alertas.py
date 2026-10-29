from datetime import datetime, timezone
from typing import List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.alerta import Alerta
from app.models.caso import Caso
from app.models.usuario import RolEnum
from app.schemas.alerta import AlertaOut, AtenderAlertaIn, ResumenAlertasOut, EscaneoOut
from app.services.integridad_service import escanear_todos, notificar_alerta

router = APIRouter(prefix="/alertas", tags=["alertas"])


def _query_visible(db: Session, usuario_actual):
    """El admin ve todas; el perito solo las de sus casos."""
    query = db.query(Alerta).join(Caso, Alerta.caso_id == Caso.id)
    if usuario_actual.rol != RolEnum.admin:
        query = query.filter(Caso.usuario_id == usuario_actual.id)
    return query


def _solo_admin(usuario_actual):
    if usuario_actual.rol != RolEnum.admin:
        raise HTTPException(status_code=403, detail="Solo un administrador puede hacer esto.")


def _a_salida(a: Alerta) -> AlertaOut:
    return AlertaOut(
        id=a.id,
        archivo_id=a.archivo_id,
        archivo_nombre=a.archivo.nombre_original,
        caso_id=a.caso_id,
        caso_numero=a.caso.numero_caso,
        tipo=a.tipo,
        ubicacion=a.ubicacion,
        hash_esperado=a.hash_esperado,
        hash_encontrado=a.hash_encontrado,
        detalle=a.detalle,
        origen=a.origen,
        correo_enviado=a.correo_enviado,
        creada_en=a.creada_en,
        atendida_en=a.atendida_en,
        atendida_por_nombre=a.atendida_por.nombre if a.atendida_por else None,
        nota_atencion=a.nota_atencion,
    )


@router.get("", response_model=List[AlertaOut])
def listar_alertas(
    estado: Optional[Literal["pendiente", "atendida"]] = None,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    query = _query_visible(db, usuario_actual)
    if estado == "pendiente":
        query = query.filter(Alerta.atendida_en.is_(None))
    elif estado == "atendida":
        query = query.filter(Alerta.atendida_en.isnot(None))
    alertas = query.order_by(Alerta.creada_en.desc()).limit(300).all()
    return [_a_salida(a) for a in alertas]


@router.get("/resumen", response_model=ResumenAlertasOut)
def resumen_alertas(
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Usado por el menú lateral para el contador de pendientes."""
    pendientes = _query_visible(db, usuario_actual).filter(Alerta.atendida_en.is_(None)).count()
    return ResumenAlertasOut(pendientes=pendientes)


@router.post("/escanear", response_model=EscaneoOut)
def escanear_ahora(
    background_tasks: BackgroundTasks,
    usuario_actual=Depends(get_current_user),
):
    """Corre el mismo escaneo que el proceso automático, a pedido (útil para la demo)."""
    _solo_admin(usuario_actual)
    revisados, nuevas = escanear_todos()
    for alerta_id in nuevas:
        background_tasks.add_task(notificar_alerta, alerta_id)
    return EscaneoOut(archivos_revisados=revisados, alertas_nuevas=len(nuevas))


@router.patch("/{alerta_id}/atender", response_model=AlertaOut)
def atender_alerta(
    alerta_id: UUID,
    payload: AtenderAlertaIn,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    _solo_admin(usuario_actual)
    alerta = db.query(Alerta).filter(Alerta.id == alerta_id).first()
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta no encontrada.")
    if alerta.atendida_en is not None:
        raise HTTPException(status_code=409, detail="La alerta ya fue atendida.")

    alerta.atendida_en = datetime.now(timezone.utc)
    alerta.atendida_por_id = usuario_actual.id
    alerta.nota_atencion = payload.nota
    db.commit()
    db.refresh(alerta)
    return _a_salida(alerta)