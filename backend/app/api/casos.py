from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from uuid import UUID

from app.db.session import get_db
from app.schemas.caso import CasoCreate, CasoOut, CasoEstadoUpdate, CasoPapeleraOut
from app.models.caso import Caso, EstadoCasoEnum
from app.models.usuario import EspecialidadEnum, RolEnum
from app.core.config import settings
from typing import List, Optional
from app.core.security import get_current_user

router = APIRouter(prefix="/casos", tags=["casos"])


def _query_visible(db: Session, usuario_actual):
    query = db.query(Caso).filter(Caso.eliminado_en.is_(None))
    if usuario_actual.rol != RolEnum.admin:
        query = query.filter(Caso.usuario_id == usuario_actual.id)
    return query


def _obtener_caso_propio(db: Session, caso_id: UUID, usuario_actual, incluir_eliminados=False) -> Caso:
    query = db.query(Caso).filter(Caso.id == caso_id)
    if not incluir_eliminados:
        query = query.filter(Caso.eliminado_en.is_(None))
    caso = query.first()
    if not caso:
        raise HTTPException(status_code=404, detail="Caso no encontrado.")
    if usuario_actual.rol != RolEnum.admin and caso.usuario_id != usuario_actual.id:
        raise HTTPException(status_code=404, detail="Caso no encontrado.")
    return caso


@router.post("", response_model=CasoOut, status_code=status.HTTP_201_CREATED)
def crear_caso(
    payload: CasoCreate,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    existe = db.query(Caso).filter(Caso.numero_caso == payload.numero_caso).first()
    if existe:
        raise HTTPException(status_code=409, detail="Ya existe un caso con ese número.")

    nuevo_caso = Caso(
        numero_caso=payload.numero_caso,
        especialidad=payload.especialidad,
        usuario_id=usuario_actual.id,
    )
    db.add(nuevo_caso)
    try:
        db.commit()
        db.refresh(nuevo_caso)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe un caso con ese número.")

    return nuevo_caso


@router.get("", response_model=List[CasoOut])
def listar_casos(
    especialidad: Optional[EspecialidadEnum] = None,
    estado: Optional[EstadoCasoEnum] = None,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    query = _query_visible(db, usuario_actual)

    if especialidad:
        query = query.filter(Caso.especialidad == especialidad)
    if estado:
        query = query.filter(Caso.estado == estado)

    return query.order_by(Caso.creado_en.desc()).all()


@router.get("/papelera", response_model=List[CasoPapeleraOut])
def listar_papelera(
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Casos eliminados hace menos de DIAS_PAPELERA días. Los más viejos
    se purgan en forma definitiva antes de armar la lista (historia Sprint 3)."""
    limite = datetime.now(timezone.utc) - timedelta(days=settings.DIAS_PAPELERA)

    vencidos = db.query(Caso).filter(Caso.eliminado_en.isnot(None), Caso.eliminado_en < limite)
    if usuario_actual.rol != RolEnum.admin:
        vencidos = vencidos.filter(Caso.usuario_id == usuario_actual.id)
    for caso in vencidos.all():
        db.delete(caso)
    db.commit()

    query = db.query(Caso).filter(Caso.eliminado_en.isnot(None), Caso.eliminado_en >= limite)
    if usuario_actual.rol != RolEnum.admin:
        query = query.filter(Caso.usuario_id == usuario_actual.id)

    resultado = []
    for caso in query.order_by(Caso.eliminado_en.desc()).all():
        vence = caso.eliminado_en + timedelta(days=settings.DIAS_PAPELERA)
        dias_restantes = max((vence - datetime.now(timezone.utc)).days, 0)
        resultado.append(
            CasoPapeleraOut(
                id=caso.id,
                numero_caso=caso.numero_caso,
                especialidad=caso.especialidad,
                estado=caso.estado,
                usuario_id=caso.usuario_id,
                creado_en=caso.creado_en,
                eliminado_en=caso.eliminado_en,
                dias_restantes=dias_restantes,
            )
        )
    return resultado


@router.get("/{caso_id}", response_model=CasoOut)
def obtener_caso(
    caso_id: UUID,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    return _obtener_caso_propio(db, caso_id, usuario_actual)


@router.patch("/{caso_id}", response_model=CasoOut)
def actualizar_estado_caso(
    caso_id: UUID,
    payload: CasoEstadoUpdate,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    caso = _obtener_caso_propio(db, caso_id, usuario_actual)
    if caso.estado == EstadoCasoEnum.cerrado:
        raise HTTPException(
            status_code=409,
            detail="El caso ya está cerrado y no admite más cambios.",
        )
    if caso.estado == payload.estado:
        raise HTTPException(status_code=400, detail="El caso ya tiene ese estado.")

    caso.estado = payload.estado
    if payload.estado == EstadoCasoEnum.cerrado:
        caso.cerrado_en = datetime.now(timezone.utc)  # Sprint 4 (historia 18)
    db.commit()
    db.refresh(caso)
    return caso


@router.delete("/{caso_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_caso(
    caso_id: UUID,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Borrado suave: el caso pasa a la papelera y se puede restaurar hasta
    DIAS_PAPELERA días después (historia Sprint 3)."""
    caso = _obtener_caso_propio(db, caso_id, usuario_actual)
    caso.eliminado_en = datetime.now(timezone.utc)
    db.commit()


@router.post("/{caso_id}/restaurar", response_model=CasoOut)
def restaurar_caso(
    caso_id: UUID,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    caso = _obtener_caso_propio(db, caso_id, usuario_actual, incluir_eliminados=True)
    if caso.eliminado_en is None:
        raise HTTPException(status_code=400, detail="El caso no está en la papelera.")
    caso.eliminado_en = None
    db.commit()
    db.refresh(caso)
    return caso