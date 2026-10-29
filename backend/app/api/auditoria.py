from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional

from app.db.session import get_db
from app.schemas.auditoria import AuditoriaItemOut
from app.models.log_custodia import LogCustodia, AccionEnum
from app.models.archivo import Archivo
from app.models.caso import Caso
from app.models.usuario import Usuario, RolEnum
from app.core.security import get_current_user

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


@router.get("", response_model=List[AuditoriaItemOut])
def panel_auditoria(
    accion: Optional[AccionEnum] = None,
    limite: int = 200,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Panel de auditoría: todos los eventos de custodia, con el caso y el
    archivo a los que pertenecen (historia Sprint 2)."""
    query = (
        db.query(LogCustodia, Archivo, Caso, Usuario)
        .join(Archivo, LogCustodia.archivo_id == Archivo.id)
        .join(Caso, Archivo.caso_id == Caso.id)
        .join(Usuario, LogCustodia.usuario_id == Usuario.id)
    )

    if usuario_actual.rol != RolEnum.admin:
        query = query.filter(
            or_(Caso.usuario_id == usuario_actual.id, LogCustodia.usuario_id == usuario_actual.id)
        )
    if accion:
        query = query.filter(LogCustodia.accion == accion)

    filas = query.order_by(LogCustodia.fecha.desc()).limit(min(limite, 500)).all()

    return [
        AuditoriaItemOut(
            id=log.id,
            fecha=log.fecha,
            accion=log.accion,
            resultado=log.resultado,
            usuario_nombre=usuario.nombre,
            archivo_id=archivo.id,
            archivo_nombre=archivo.nombre_original,
            caso_id=caso.id,
            caso_numero=caso.numero_caso,
        )
        for log, archivo, caso, usuario in filas
    ]
