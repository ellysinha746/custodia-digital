import hashlib
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.log_custodia import LogCustodia, AccionEnum
from app.models.archivo import Archivo
from app.models.caso import Caso
from app.models.usuario import Usuario, RolEnum
from app.models.reporte_auditoria import ReporteAuditoria
from app.services.reporte_service import (
    hash_contenido,
    firmar,
    firma_valida,
    generar_csv,
    generar_pdf,
)

router = APIRouter(prefix="/auditoria/reporte", tags=["reporte de auditoría"])

MAX_EVENTOS = 5000


class VerificacionReporteOut(BaseModel):
    valido: bool
    mensaje: str
    folio: Optional[str] = None
    formato: Optional[str] = None
    generado_en: Optional[datetime] = None
    generado_por: Optional[str] = None
    total_eventos: Optional[int] = None


def _eventos_visibles(db: Session, usuario_actual, accion: Optional[AccionEnum]):
    """Mismos eventos que ve el panel de auditoría (admin: todos; perito: los suyos)."""
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
    filas = query.order_by(LogCustodia.fecha.desc()).limit(MAX_EVENTOS).all()
    return [
        {
            "fecha": log.fecha.astimezone(timezone.utc).isoformat(),
            "accion": log.accion.value,
            "resultado": log.resultado,
            "usuario": usuario.nombre,
            "caso": caso.numero_caso,
            "archivo": archivo.nombre_original,
        }
        for log, archivo, caso, usuario in filas
    ]


@router.get("")
def exportar_reporte(
    formato: Literal["pdf", "csv"] = "pdf",
    accion: Optional[AccionEnum] = None,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Historia 16: exporta el panel de auditoría con sello de tiempo firmado."""
    eventos = _eventos_visibles(db, usuario_actual, accion)
    generado_en = datetime.now(timezone.utc)
    folio = f"AUD-{generado_en:%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
    h_eventos = hash_contenido(eventos)
    firma = firmar(folio, generado_en, h_eventos)

    meta = {
        "folio": folio,
        "generado_en": generado_en,
        "generado_por": usuario_actual.nombre,
        "filtro": accion.value if accion else None,
        "hash_contenido": h_eventos,
        "firma": firma,
    }
    contenido = generar_pdf(eventos, meta) if formato == "pdf" else generar_csv(eventos, meta)

    db.add(
        ReporteAuditoria(
            folio=folio,
            formato=formato,
            filtros={"accion": meta["filtro"]},
            total_eventos=len(eventos),
            hash_contenido=h_eventos,
            hash_archivo=hashlib.sha256(contenido).hexdigest(),
            firma=firma,
            generado_en=generado_en,
            generado_por_id=usuario_actual.id,
        )
    )
    db.commit()

    return Response(
        content=contenido,
        media_type="application/pdf" if formato == "pdf" else "text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="reporte_auditoria_{folio}.{formato}"',
            "X-Folio": folio,
            "Access-Control-Expose-Headers": "X-Folio",
        },
    )


@router.post("/verificar", response_model=VerificacionReporteOut)
async def verificar_reporte(
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Comprueba que un reporte descargado es auténtico y no fue modificado."""
    contenido = await archivo.read()
    h = hashlib.sha256(contenido).hexdigest()
    reporte = db.query(ReporteAuditoria).filter(ReporteAuditoria.hash_archivo == h).first()

    if not reporte:
        return VerificacionReporteOut(
            valido=False,
            mensaje="El archivo no coincide con ningún reporte emitido por el sistema: fue modificado o no es un reporte original.",
        )
    if not firma_valida(reporte.folio, reporte.generado_en, reporte.hash_contenido, reporte.firma):
        return VerificacionReporteOut(
            valido=False,
            mensaje="El registro del reporte existe, pero su sello no es válido.",
            folio=reporte.folio,
        )
    return VerificacionReporteOut(
        valido=True,
        mensaje="Reporte auténtico: no fue modificado desde su emisión.",
        folio=reporte.folio,
        formato=reporte.formato,
        generado_en=reporte.generado_en,
        generado_por=reporte.generado_por.nombre,
        total_eventos=reporte.total_eventos,
    )
