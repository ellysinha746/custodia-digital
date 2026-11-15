import hashlib
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.config import settings
from app.core.security import get_current_user
from app.core.permisos import condicion_casos_visibles, VEN_TODO
from app.services import tsa_service  # Sprint 6 (historia 21)
from app.models.log_custodia import LogCustodia, AccionEnum
from app.models.archivo import Archivo
from app.models.caso import Caso
from app.models.usuario import Usuario
from app.models.reporte_auditoria import ReporteAuditoria
from app.services.reporte_service import (
    hash_contenido,
    firmar,
    firma_valida,
    generar_csv,
    generar_pdf,
    mensaje_sello,
)

router = APIRouter(prefix="/auditoria/reporte", tags=["reporte de auditoría"])

MAX_EVENTOS = 5000


class SelloTsaOut(BaseModel):
    """Sprint 6 (historia 21): estado del sello RFC 3161 del reporte."""
    presente: bool
    valido: bool = False
    mensaje: str
    fecha: Optional[datetime] = None
    serie: Optional[str] = None
    tsa: Optional[str] = None


class VerificacionReporteOut(BaseModel):
    valido: bool
    mensaje: str
    folio: Optional[str] = None
    formato: Optional[str] = None
    generado_en: Optional[datetime] = None
    generado_por: Optional[str] = None
    total_eventos: Optional[int] = None
    sello_tsa: Optional[SelloTsaOut] = None  # Sprint 6 (historia 21)


def _eventos_visibles(db: Session, usuario_actual, accion: Optional[AccionEnum]):
    """Mismos eventos que ve el panel de auditoría (admin: todos; perito: los suyos)."""
    query = (
        db.query(LogCustodia, Archivo, Caso, Usuario)
        .join(Archivo, LogCustodia.archivo_id == Archivo.id)
        .join(Caso, Archivo.caso_id == Caso.id)
        .join(Usuario, LogCustodia.usuario_id == Usuario.id)
    )
    # Sprint 5: cada rol ve los eventos de los casos que puede ver, más los propios.
    query = query.filter(
        or_(condicion_casos_visibles(usuario_actual), LogCustodia.usuario_id == usuario_actual.id)
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
    # Sprint 6 (historia 21): sello RFC 3161 de una TSA externa (None si no respondió).
    sello_tsa = tsa_service.sellar(mensaje_sello(folio, generado_en, h_eventos))

    meta = {
        "folio": folio,
        "generado_en": generado_en,
        "generado_por": usuario_actual.nombre,
        "filtro": accion.value if accion else None,
        "hash_contenido": h_eventos,
        "firma": firma,
        "tsa": sello_tsa,
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
            tsa_token=sello_tsa.token if sello_tsa else None,
            tsa_fecha=sello_tsa.fecha if sello_tsa else None,
            tsa_serie=sello_tsa.serie if sello_tsa else None,
        )
    )
    db.commit()

    return Response(
        content=contenido,
        media_type="application/pdf" if formato == "pdf" else "text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="reporte_auditoria_{folio}.{formato}"',
            "X-Folio": folio,
            "X-Sello-Tsa": "si" if sello_tsa else "no",  # Sprint 6 (historia 21)
            "Access-Control-Expose-Headers": "X-Folio, X-Sello-Tsa",
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
        # openssl corre fuera del bucle de eventos (este endpoint es async)
        sello_tsa=await run_in_threadpool(_sello_tsa_out, reporte),
    )


# ---------------------------------------------------------------------------
# Sprint 6 (historia 21): sello de tiempo RFC 3161.

def _sello_tsa_out(reporte: ReporteAuditoria) -> SelloTsaOut:
    if not reporte.tsa_token:
        return SelloTsaOut(
            presente=False,
            mensaje="Este reporte no tiene sello RFC 3161: se emitió antes de esta función o la TSA no respondió.",
        )
    datos = mensaje_sello(reporte.folio, reporte.generado_en, reporte.hash_contenido)
    valido = tsa_service.verificar(datos, reporte.tsa_token)
    return SelloTsaOut(
        presente=True,
        valido=valido,
        mensaje=(
            "Sello RFC 3161 válido: una autoridad externa certifica que el reporte existía en esa fecha."
            if valido else "El sello RFC 3161 NO corresponde a los datos del reporte."
        ),
        fecha=reporte.tsa_fecha,
        serie=reporte.tsa_serie,
        tsa=settings.TSA_NOMBRE,
    )


@router.get("/{folio}/sello-tiempo")
def descargar_sello_reporte(
    folio: str,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """ZIP para verificar el sello RFC 3161 con OpenSSL, sin depender de CustodiaDigital."""
    reporte = db.query(ReporteAuditoria).filter(ReporteAuditoria.folio == folio).first()
    # Lo descarga quien emitió el reporte, o el jefe y el fiscal (ven toda la auditoría).
    if not reporte or (reporte.generado_por_id != usuario_actual.id and usuario_actual.rol not in VEN_TODO):
        raise HTTPException(status_code=404, detail="Reporte no encontrado.")
    if not reporte.tsa_token:
        raise HTTPException(
            status_code=404,
            detail="Este reporte no tiene sello RFC 3161 (se emitió antes de esta función o la TSA no respondió).",
        )
    contenido = tsa_service.paquete_zip(
        mensaje_sello(reporte.folio, reporte.generado_en, reporte.hash_contenido),
        reporte.tsa_token,
        f"Reporte de auditoría {reporte.folio} (SHA-256 de los eventos y firma del servidor).",
        reporte.tsa_fecha,
        reporte.tsa_serie,
        settings.TSA_NOMBRE,
    )
    return Response(
        content=contenido,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="sello_rfc3161_{folio}.zip"'},
    )
