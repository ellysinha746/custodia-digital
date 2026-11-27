"""Sprint 8 (historia 40): transcripción de audio y video con Whisper (local)."""
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.archivos import _obtener_archivo
from app.core.permisos import exigir
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.archivo import EstadoProcesamientoEnum
from app.models.log_custodia import AccionEnum, LogCustodia
from app.schemas.archivo import ArchivoOut
from app.services import transcripcion_service

router = APIRouter(tags=["transcripción (Whisper)"])


class TranscripcionOut(BaseModel):
    estado: Optional[str] = None
    segmentos: List[Dict] = []
    idioma: Optional[str] = None
    duracion: Optional[float] = None
    motor: Optional[str] = None
    transcrito_en: Optional[datetime] = None
    sha256: Optional[str] = None
    integra: Optional[bool] = None   # el texto guardado sigue coincidiendo con su huella
    error: Optional[str] = None


@router.get("/archivos/{archivo_id}/transcripcion", response_model=TranscripcionOut)
def ver(archivo_id: UUID, db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    a = _obtener_archivo(db, archivo_id, usuario_actual)
    integra = None
    if a.transcripcion_estado == "listo":
        integra = transcripcion_service.huella(a.transcripcion_texto) == a.transcripcion_sha256
    return TranscripcionOut(
        estado=a.transcripcion_estado, segmentos=a.transcripcion_segmentos or [], idioma=a.transcripcion_idioma,
        duracion=a.transcripcion_duracion, motor=a.transcripcion_motor, transcrito_en=a.transcripcion_en,
        sha256=a.transcripcion_sha256, integra=integra, error=a.transcripcion_error,
    )


@router.post("/archivos/{archivo_id}/transcripcion", response_model=ArchivoOut, status_code=202)
def transcribir(
    archivo_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """(Re)transcribe en segundo plano: audios largos, evidencia anterior o un intento que falló."""
    exigir(usuario_actual, "verificar_integridad")
    archivo = _obtener_archivo(db, archivo_id, usuario_actual)
    if archivo.estado_procesamiento != EstadoProcesamientoEnum.listo:
        raise HTTPException(status_code=409, detail="El archivo aún se está procesando.")
    if archivo.transcripcion_estado in ("pendiente", "procesando"):
        raise HTTPException(status_code=409, detail="Este audio ya se está transcribiendo.")
    if not transcripcion_service.preparar(archivo):
        raise HTTPException(status_code=415, detail="Solo se pueden transcribir archivos de audio o video.")
    db.commit()
    db.refresh(archivo)
    background_tasks.add_task(transcripcion_service.procesar, archivo.id, usuario_actual.id)
    return archivo


@router.get("/archivos/{archivo_id}/transcripcion.txt")
def descargar(archivo_id: UUID, db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    """La transcripción con marcas de tiempo, para adjuntar al informe pericial."""
    a = _obtener_archivo(db, archivo_id, usuario_actual)
    if a.transcripcion_estado != "listo":
        raise HTTPException(status_code=404, detail="Este archivo todavía no tiene transcripción.")
    db.add(LogCustodia(archivo_id=a.id, usuario_id=usuario_actual.id, accion=AccionEnum.descarga,
                       resultado="descarga de la transcripción (Whisper)"))
    db.commit()
    nombre = a.nombre_original.rsplit(".", 1)[0] + "_transcripcion.txt"
    return Response(
        content=transcripcion_service.a_texto_con_tiempos(a).encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
