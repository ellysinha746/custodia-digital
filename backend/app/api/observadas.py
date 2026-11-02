import os
import shutil
import uuid
from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.api.archivos import _obtener_archivo, _obtener_caso_editable
from app.models.version_observada import VersionObservada
from app.models.log_custodia import LogCustodia, AccionEnum
from app.services.hashing_service import calcular_sha256
from app.services.storage_service import STORAGE_DIR

router = APIRouter(tags=["versiones observadas"])


class VersionObservadaOut(BaseModel):
    id: UUID
    archivo_id: UUID
    nombre: str
    hash_sha256: str
    observaciones: str
    subido_por_nombre: str
    subido_en: datetime


def _a_salida(v: VersionObservada) -> VersionObservadaOut:
    return VersionObservadaOut(
        id=v.id,
        archivo_id=v.archivo_id,
        nombre=v.nombre,
        hash_sha256=v.hash_sha256,
        observaciones=v.observaciones,
        subido_por_nombre=v.subido_por.nombre,
        subido_en=v.subido_en,
    )


@router.post(
    "/archivos/{archivo_id}/observadas",
    response_model=VersionObservadaOut,
    status_code=status.HTTP_201_CREATED,
)
def subir_version_observada(
    archivo_id: UUID,
    archivo: UploadFile = File(...),
    observaciones: str = Form(...),
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Historia 14: otro perito sube su versión del archivo con observaciones.
    Se guarda en una carpeta propia: el original y la copia NO se tocan."""
    evidencia = _obtener_archivo(db, archivo_id, usuario_actual)
    _obtener_caso_editable(db, evidencia.caso_id, usuario_actual)
    if not observaciones.strip():
        raise HTTPException(status_code=400, detail="Escribe las observaciones de esta versión.")

    carpeta = os.path.join(STORAGE_DIR, str(evidencia.caso_id), "observadas", str(evidencia.id), uuid.uuid4().hex)
    os.makedirs(carpeta, exist_ok=True)
    nombre = os.path.basename(archivo.filename or "observada")
    ruta = os.path.join(carpeta, nombre)
    with open(ruta, "wb") as destino:
        shutil.copyfileobj(archivo.file, destino)

    version = VersionObservada(
        archivo_id=evidencia.id,
        nombre=nombre,
        ruta=ruta,
        hash_sha256=calcular_sha256(ruta),
        observaciones=observaciones.strip(),
        subido_por_id=usuario_actual.id,
    )
    db.add(version)
    db.add(
        LogCustodia(
            archivo_id=evidencia.id,
            usuario_id=usuario_actual.id,
            accion=AccionEnum.subida,
            resultado="version_observada",
        )
    )
    db.commit()
    db.refresh(version)
    return _a_salida(version)


@router.get("/archivos/{archivo_id}/observadas", response_model=List[VersionObservadaOut])
def listar_versiones_observadas(
    archivo_id: UUID,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    evidencia = _obtener_archivo(db, archivo_id, usuario_actual)
    versiones = (
        db.query(VersionObservada)
        .filter(VersionObservada.archivo_id == evidencia.id)
        .order_by(VersionObservada.subido_en.desc())
        .all()
    )
    return [_a_salida(v) for v in versiones]


@router.get("/observadas/{version_id}/descargar")
def descargar_version_observada(
    version_id: UUID,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    version = db.query(VersionObservada).filter(VersionObservada.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Versión no encontrada.")
    # Hereda la visibilidad del archivo (dueño del caso o admin).
    evidencia = _obtener_archivo(db, version.archivo_id, usuario_actual)
    if not os.path.exists(version.ruta):
        raise HTTPException(status_code=404, detail="La versión ya no está en el almacenamiento.")

    db.add(
        LogCustodia(
            archivo_id=evidencia.id,
            usuario_id=usuario_actual.id,
            accion=AccionEnum.descarga,
            resultado="observada",
        )
    )
    db.commit()
    return FileResponse(version.ruta, filename=f"OBSERVADA_{version.nombre}")