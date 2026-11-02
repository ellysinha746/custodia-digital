import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional

from app.db.session import get_db, SessionLocal
from app.schemas.archivo import (
    ArchivoOut,
    MetadatosUpdate,
    VerificacionOut,
    LogCustodiaOut,
)
from app.models.caso import Caso, EstadoCasoEnum
from app.models.archivo import Archivo, EstadoProcesamientoEnum
from app.models.log_custodia import LogCustodia, AccionEnum
from app.models.usuario import RolEnum
from app.core.config import settings
from app.core.security import get_current_user
from app.services.storage_service import guardar_archivo
from app.services.hashing_service import calcular_sha256
from app.services.integridad_service import revisar_archivo, notificar_alerta
from app.services.ficha_service import normalizar_ficha
router = APIRouter(tags=["archivos"])


def _obtener_caso(db: Session, caso_id: UUID, usuario_actual) -> Caso:
    """Caso visible para este usuario. Un caso en papelera no existe para nadie
    salvo a través de los endpoints propios de la papelera."""
    caso = db.query(Caso).filter(Caso.id == caso_id, Caso.eliminado_en.is_(None)).first()
    if not caso:
        raise HTTPException(status_code=404, detail="Caso no encontrado.")
    if usuario_actual.rol != RolEnum.admin and caso.usuario_id != usuario_actual.id:
        raise HTTPException(status_code=404, detail="Caso no encontrado.")
    return caso


def _obtener_caso_editable(db: Session, caso_id: UUID, usuario_actual) -> Caso:
    """Igual que _obtener_caso, pero además bloquea escrituras sobre un caso
    cerrado (evita alterar evidencia de un expediente ya cerrado)."""
    caso = _obtener_caso(db, caso_id, usuario_actual)
    if caso.estado == EstadoCasoEnum.cerrado:
        raise HTTPException(
            status_code=409,
            detail="El caso está cerrado: no se pueden registrar más cambios.",
        )
    return caso


def _obtener_archivo(db: Session, archivo_id: UUID, usuario_actual) -> Archivo:
    archivo = db.query(Archivo).filter(Archivo.id == archivo_id).first()
    if not archivo:
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    # Un archivo hereda la visibilidad de su caso (dueño o admin, caso no eliminado).
    _obtener_caso(db, archivo.caso_id, usuario_actual)
    return archivo


def _procesar_hash_en_segundo_plano(archivo_id: UUID, ruta_copia: str) -> None:
    """Corre después de responder al cliente: calcula el hash de archivos
    pesados sin bloquear la subida (historia Sprint 2)."""
    db = SessionLocal()
    try:
        archivo = db.query(Archivo).filter(Archivo.id == archivo_id).first()
        if not archivo:
            return
        hash_calculado = calcular_sha256(ruta_copia)
        archivo.hash_original = hash_calculado
        archivo.hash_actual = hash_calculado
        archivo.estado_procesamiento = EstadoProcesamientoEnum.listo
        db.add(
            LogCustodia(
                archivo_id=archivo.id,
                usuario_id=archivo.caso.usuario_id,
                accion=AccionEnum.subida,
                resultado="listo",
            )
        )
        db.commit()
    finally:
        db.close()


@router.post(
    "/casos/{caso_id}/archivos",
    response_model=ArchivoOut,
    status_code=status.HTTP_201_CREATED,
)
def subir_archivo(
    caso_id: UUID,
    background_tasks: BackgroundTasks,
    archivo: UploadFile = File(...),
    imei: Optional[str] = Form(None),
    modelo: Optional[str] = Form(None),
    mac: Optional[str] = Form(None),
    sistema_operativo: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    caso = _obtener_caso_editable(db, caso_id, usuario_actual)

    # Sprint 4 (historia 13): ficha opcional del dispositivo. Se valida ANTES
    # de guardar nada en disco, para no dejar archivos huérfanos si es inválida.
    ficha = normalizar_ficha(
        {"imei": imei, "modelo": modelo, "mac": mac, "sistema_operativo": sistema_operativo}
    )
    datos_ficha = {
        "ficha_dispositivo": ficha or None,
        "ficha_registrada_en": datetime.now(timezone.utc) if ficha else None,
    }
    ruta_original, ruta_copia = guardar_archivo(
        str(caso_id), archivo.filename, archivo.file
    )
    tamano_mb = os.path.getsize(ruta_copia) / (1024 * 1024)
    es_pesado = tamano_mb >= settings.UMBRAL_ARCHIVO_PESADO_MB

    if es_pesado:
        nuevo = Archivo(
            caso_id=caso_id,
            nombre_original=archivo.filename,
            ruta_original=ruta_original,
            ruta_copia_trabajo=ruta_copia,
            hash_original=None,
            hash_actual=None,
            estado_procesamiento=EstadoProcesamientoEnum.procesando,
            metadatos={"content_type": archivo.content_type},
            **datos_ficha,
        )
        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)
        background_tasks.add_task(_procesar_hash_en_segundo_plano, nuevo.id, ruta_copia)
        return nuevo

    hash_copia = calcular_sha256(ruta_copia)
    nuevo = Archivo(
        caso_id=caso_id,
        nombre_original=archivo.filename,
        ruta_original=ruta_original,
        ruta_copia_trabajo=ruta_copia,
        hash_original=hash_copia,
        hash_actual=hash_copia,
        estado_procesamiento=EstadoProcesamientoEnum.listo,
        metadatos={"content_type": archivo.content_type},
        **datos_ficha,
    )
    db.add(nuevo)
    db.flush()
    db.add(
        LogCustodia(
            archivo_id=nuevo.id,
            usuario_id=usuario_actual.id,
            accion=AccionEnum.subida,
            resultado="listo",
        )
    )
    db.commit()
    db.refresh(nuevo)
    return nuevo


@router.get("/casos/{caso_id}/archivos", response_model=List[ArchivoOut])
def listar_archivos(
    caso_id: UUID,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    _obtener_caso(db, caso_id, usuario_actual)
    return (
        db.query(Archivo)
        .filter(Archivo.caso_id == caso_id)
        .order_by(Archivo.subido_en.desc())
        .all()
    )


@router.get("/archivos/{archivo_id}", response_model=ArchivoOut)
def obtener_archivo(
    archivo_id: UUID,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Usado por el frontend para hacer polling mientras estado_procesamiento
    sigue en 'procesando' (historia de notificación, Sprint 2)."""
    return _obtener_archivo(db, archivo_id, usuario_actual)


@router.get("/archivos/{archivo_id}/historial", response_model=List[LogCustodiaOut])
def historial_archivo(
    archivo_id: UUID,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    archivo = _obtener_archivo(db, archivo_id, usuario_actual)
    logs = (
        db.query(LogCustodia)
        .filter(LogCustodia.archivo_id == archivo.id)
        .order_by(LogCustodia.fecha.desc())
        .all()
    )
    return [
        LogCustodiaOut(
            id=log.id,
            archivo_id=log.archivo_id,
            usuario_id=log.usuario_id,
            usuario_nombre=log.usuario.nombre,
            accion=log.accion,
            resultado=log.resultado,
            fecha=log.fecha,
        )
        for log in logs
    ]


@router.get("/archivos/{archivo_id}/descargar")
def descargar_archivo(
    archivo_id: UUID,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    archivo = _obtener_archivo(db, archivo_id, usuario_actual)
    if archivo.estado_procesamiento != EstadoProcesamientoEnum.listo:
        raise HTTPException(status_code=409, detail="El archivo aún se está procesando.")
    if not os.path.exists(archivo.ruta_copia_trabajo):
        raise HTTPException(status_code=404, detail="El archivo ya no está en el almacenamiento.")

    db.add(
        LogCustodia(
            archivo_id=archivo.id,
            usuario_id=usuario_actual.id,
            accion=AccionEnum.descarga,
        )
    )
    db.commit()

    # Siempre se entrega la copia de trabajo: el original nunca se expone ni se toca.
    return FileResponse(archivo.ruta_copia_trabajo, filename=archivo.nombre_original)


@router.post("/archivos/{archivo_id}/verificar", response_model=VerificacionOut)
def verificar_integridad(
    archivo_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    archivo = _obtener_archivo(db, archivo_id, usuario_actual)
    if archivo.estado_procesamiento != EstadoProcesamientoEnum.listo or not archivo.hash_original:
        raise HTTPException(
            status_code=409,
            detail="El archivo aún no tiene un hash original calculado.",
        )
    
    # Sprint 4: se revisan el original y la copia; si alguno cambió sin
    # respaldo, revisar_archivo deja creada la alerta.
    resultado, hash_original_hoy, hash_copia_hoy, alerta = revisar_archivo(
        db, archivo, origen="verificacion_manual"
    )

    archivo.hash_actual = hash_copia_hoy

    log = LogCustodia(
        archivo_id=archivo.id,
        usuario_id=usuario_actual.id,
        accion=AccionEnum.verificacion,
        resultado=resultado,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    if alerta:
        background_tasks.add_task(notificar_alerta, alerta.id)

    return VerificacionOut(
        archivo_id=archivo.id,
        resultado=resultado,
        hash_original=archivo.hash_original,
        hash_actual=hash_original_hoy,
        hash_copia=hash_copia_hoy,
        alerta_id=alerta.id if alerta else None,
        verificado_en=log.fecha,
    )


@router.patch("/archivos/{archivo_id}/metadatos", response_model=ArchivoOut)
def actualizar_metadatos(
    archivo_id: UUID,
    payload: MetadatosUpdate,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    archivo = _obtener_archivo(db, archivo_id, usuario_actual)
    _obtener_caso_editable(db, archivo.caso_id, usuario_actual)

    metadatos_actuales = dict(archivo.metadatos or {})
    metadatos_actuales.update(payload.metadatos)
    archivo.metadatos = metadatos_actuales
    db.commit()
    db.refresh(archivo)
    return archivo
