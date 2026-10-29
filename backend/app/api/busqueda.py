from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.busqueda import BusquedaOut, ArchivoBusquedaOut
from app.schemas.caso import CasoOut
from app.models.caso import Caso
from app.models.archivo import Archivo
from app.models.usuario import RolEnum
from app.core.security import get_current_user

router = APIRouter(tags=["busqueda"])


@router.get("/buscar", response_model=BusquedaOut)
def buscar(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Buscador instantáneo por número de caso o nombre de archivo
    (historia Sprint 2: 'quiero un buscador instantáneo por código o nombre
    de archivo, para encontrar un expediente de manera inmediata')."""
    patron = f"%{q}%"

    casos_query = db.query(Caso).filter(
        Caso.eliminado_en.is_(None), Caso.numero_caso.ilike(patron)
    )
    if usuario_actual.rol != RolEnum.admin:
        casos_query = casos_query.filter(Caso.usuario_id == usuario_actual.id)
    casos = casos_query.order_by(Caso.creado_en.desc()).limit(10).all()

    archivos_query = (
        db.query(Archivo, Caso)
        .join(Caso, Archivo.caso_id == Caso.id)
        .filter(Caso.eliminado_en.is_(None), Archivo.nombre_original.ilike(patron))
    )
    if usuario_actual.rol != RolEnum.admin:
        archivos_query = archivos_query.filter(Caso.usuario_id == usuario_actual.id)
    filas = archivos_query.order_by(Archivo.subido_en.desc()).limit(10).all()

    archivos = [
        ArchivoBusquedaOut(
            id=archivo.id,
            caso_id=archivo.caso_id,
            nombre_original=archivo.nombre_original,
            hash_original=archivo.hash_original,
            hash_actual=archivo.hash_actual,
            metadatos=archivo.metadatos,
            estado_procesamiento=archivo.estado_procesamiento,
            subido_en=archivo.subido_en,
            caso_numero=caso.numero_caso,
        )
        for archivo, caso in filas
    ]

    return BusquedaOut(
        casos=[CasoOut.model_validate(c) for c in casos],
        archivos=archivos,
    )
