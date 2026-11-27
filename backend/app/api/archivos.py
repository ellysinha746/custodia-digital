import os
import shutil
import tempfile
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Literal, Optional

from app.db.session import get_db, SessionLocal
from app.schemas.archivo import (
    ArchivoOut,
    MetadatosUpdate,
    VerificacionOut,
    LogCustodiaOut,
    CotejoIn,
    CotejoOut,
)
from app.models.caso import Caso, EstadoCasoEnum
from app.models.archivo import Archivo, EstadoProcesamientoEnum
from app.models.log_custodia import LogCustodia, AccionEnum
from app.core.config import settings
from app.core.security import get_current_user
from app.core.permisos import puede_ver_caso, exigir
from app.services.storage_service import guardar_archivo, existe, tamano, abrir, respuesta_descarga, descripcion
from app.services.metadatos_service import extraer_metadatos
from app.services.validacion_subida import validar_extension, copiar_con_limite, validar_contenido
from app.services.hashing_service import calcular_sha256, calcular_hashes
from app.services.integridad_service import revisar_archivo, notificar_alerta
from app.services import cotejo_service  # Sprint 6 (historia 23)
from app.services import ocr_service  # Sprint 7 (historia 29)
from app.services import transcripcion_service  # Sprint 8 (historia 40)
from app.services.ficha_service import normalizar_ficha
from app.services import virustotal_service  # Sprint 8 (historia 38)
router = APIRouter(tags=["archivos"])


def _obtener_caso(db: Session, caso_id: UUID, usuario_actual) -> Caso:
    """Caso visible para este usuario. Un caso en papelera no existe para nadie
    salvo a través de los endpoints propios de la papelera."""
    caso = db.query(Caso).filter(Caso.id == caso_id, Caso.eliminado_en.is_(None)).first()
    if not caso:
        raise HTTPException(status_code=404, detail="Caso no encontrado.")
    if not puede_ver_caso(db, usuario_actual, caso):
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
        hashes = calcular_hashes(ruta_copia)  # Sprint 6 (historia 23): SHA-256 + SHA-1 + MD5
        archivo.hash_original = hashes["sha256"]
        archivo.hash_actual = hashes["sha256"]
        archivo.hash_sha1 = hashes["sha1"]
        archivo.hash_md5 = hashes["md5"]
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
    exigir(usuario_actual, "subir_evidencia")
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
    # Sprint 6: el archivo se recibe primero en un temporal para extraer sus
    # metadatos técnicos (historia 20) y luego va al almacenamiento, sea disco o
    # S3/MinIO (historia 22).
    validar_extension(archivo.filename)  # Sprint 6 (historia 27)
    with tempfile.NamedTemporaryFile(prefix="subida_", delete=False) as tmp:
        ruta_tmp = tmp.name
        try:
            copiar_con_limite(archivo.file, tmp)  # Sprint 6 (historia 27)
        except HTTPException:
            tmp.close()
            os.remove(ruta_tmp)
            raise
    try:
        metadatos_tecnicos = extraer_metadatos(ruta_tmp, archivo.filename)
        validar_contenido(metadatos_tecnicos)  # Sprint 6 (historia 27)
        with open(ruta_tmp, "rb") as origen:
            ruta_original, ruta_copia = guardar_archivo(str(caso_id), archivo.filename, origen)
    finally:
        os.remove(ruta_tmp)
    metadatos_tecnicos["almacenamiento"] = descripcion(ruta_original)
    tamano_mb = metadatos_tecnicos["tamano_bytes"] / (1024 * 1024)
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
            metadatos_tecnicos=metadatos_tecnicos,
            **datos_ficha,
        )
        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)
        background_tasks.add_task(_procesar_hash_en_segundo_plano, nuevo.id, ruta_copia)
        _programar_ocr(db, nuevo, usuario_actual, background_tasks)  # Sprint 7 (historia 29)
        return nuevo

    hashes = calcular_hashes(ruta_copia)  # Sprint 6 (historia 23): SHA-256 + SHA-1 + MD5
    nuevo = Archivo(
        caso_id=caso_id,
        nombre_original=archivo.filename,
        ruta_original=ruta_original,
        ruta_copia_trabajo=ruta_copia,
        hash_original=hashes["sha256"],
        hash_actual=hashes["sha256"],
        hash_sha1=hashes["sha1"],
        hash_md5=hashes["md5"],
        estado_procesamiento=EstadoProcesamientoEnum.listo,
        metadatos={"content_type": archivo.content_type},
        metadatos_tecnicos=metadatos_tecnicos,
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
    _programar_ocr(db, nuevo, usuario_actual, background_tasks)  # Sprint 7 (historia 29)
    return nuevo


def _programar_ocr(db: Session, archivo: Archivo, usuario_actual, background_tasks: BackgroundTasks) -> None:
    """Sprint 7 (historia 29): imágenes y PDFs se leen con OCR en segundo plano, después de responder."""
    if settings.OCR_AUTOMATICO and ocr_service.preparar(archivo):
        db.commit()
        db.refresh(archivo)
        background_tasks.add_task(ocr_service.procesar, archivo.id, usuario_actual.id)
    # Sprint 8 (historia 40): audio y video se transcriben con Whisper (los muy largos, a pedido).
    duracion = transcripcion_service.duracion_segundos(archivo)
    corto = duracion is None or duracion <= settings.WHISPER_MAX_MINUTOS * 60
    if settings.WHISPER_AUTOMATICO and corto and transcripcion_service.preparar(archivo):
        db.commit()
        db.refresh(archivo)
        background_tasks.add_task(transcripcion_service.procesar, archivo.id, usuario_actual.id)


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
    version: Literal["copia", "original"] = "copia",
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Sprint 4 (historia 14): el perito elige descargar la copia de trabajo
    o el original. El original solo se entrega si su hash sigue intacto."""
    archivo = _obtener_archivo(db, archivo_id, usuario_actual)
    if version == "original":
        exigir(usuario_actual, "descargar_original")
    if archivo.estado_procesamiento != EstadoProcesamientoEnum.listo:
        raise HTTPException(status_code=409, detail="El archivo aún se está procesando.")

    ruta = archivo.ruta_original if version == "original" else archivo.ruta_copia_trabajo
    if not existe(ruta):
        raise HTTPException(status_code=404, detail="El archivo ya no está en el almacenamiento.")
    if version == "original" and calcular_sha256(ruta) != archivo.hash_original:
        raise HTTPException(
            status_code=409,
            detail="El original no coincide con su hash registrado: no se entrega. Revisa las alertas de integridad.",
        )

    db.add(
        LogCustodia(
            archivo_id=archivo.id,
            usuario_id=usuario_actual.id,
            accion=AccionEnum.descarga,
            resultado=version,
        )
    )
    db.commit()

    nombre = archivo.nombre_original if version == "copia" else f"ORIGINAL_{archivo.nombre_original}"
    # El original se lee pero nunca se modifica: solo se entrega (disco o S3).
    return respuesta_descarga(ruta, nombre)


@router.post("/archivos/{archivo_id}/metadatos-tecnicos", response_model=ArchivoOut)
def reextraer_metadatos(
    archivo_id: UUID,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Sprint 6 (historia 20): vuelve a extraer los metadatos técnicos leyendo el
    ORIGINAL (solo lectura). Sirve para evidencia subida antes del Sprint 6."""
    exigir(usuario_actual, "editar_metadatos")
    archivo = _obtener_archivo(db, archivo_id, usuario_actual)
    if not existe(archivo.ruta_original):
        raise HTTPException(status_code=404, detail="El original ya no está en el almacenamiento.")

    with tempfile.NamedTemporaryFile(prefix="meta_", delete=False) as tmp:
        with abrir(archivo.ruta_original) as origen:
            shutil.copyfileobj(origen, tmp)
        ruta_tmp = tmp.name
    try:
        metadatos_tecnicos = extraer_metadatos(ruta_tmp, archivo.nombre_original)
    finally:
        os.remove(ruta_tmp)
    metadatos_tecnicos["almacenamiento"] = descripcion(archivo.ruta_original)
    archivo.metadatos_tecnicos = metadatos_tecnicos
    db.add(
        LogCustodia(
            archivo_id=archivo.id,
            usuario_id=usuario_actual.id,
            accion=AccionEnum.acceso,
            resultado="metadatos técnicos re-extraídos",
        )
    )
    db.commit()
    db.refresh(archivo)
    return archivo


@router.post("/archivos/{archivo_id}/verificar", response_model=VerificacionOut)
def verificar_integridad(
    archivo_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    exigir(usuario_actual, "verificar_integridad")
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
    exigir(usuario_actual, "editar_metadatos")
    archivo = _obtener_archivo(db, archivo_id, usuario_actual)
    _obtener_caso_editable(db, archivo.caso_id, usuario_actual)

    metadatos_actuales = dict(archivo.metadatos or {})
    metadatos_actuales.update(payload.metadatos)
    archivo.metadatos = metadatos_actuales
    db.commit()
    db.refresh(archivo)
    return archivo


# ---------------------------------------------------------------------------
# Sprint 6 (historia 23): doble hash y cotejo con Cellebrite / FTK Imager.

def _archivo_listo(db: Session, archivo_id: UUID, usuario_actual) -> Archivo:
    exigir(usuario_actual, "verificar_integridad")
    archivo = _obtener_archivo(db, archivo_id, usuario_actual)
    if archivo.estado_procesamiento != EstadoProcesamientoEnum.listo or not archivo.hash_original:
        raise HTTPException(status_code=409, detail="El archivo aún no tiene un hash original calculado.")
    return archivo


@router.post("/archivos/{archivo_id}/hashes-adicionales", response_model=ArchivoOut)
def calcular_hashes_adicionales(
    archivo_id: UUID,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """SHA-1 y MD5 de evidencia subida antes de la historia 23 (se leen del original)."""
    archivo = _archivo_listo(db, archivo_id, usuario_actual)
    if cotejo_service.asegurar_hashes_adicionales(archivo):
        db.add(
            LogCustodia(
                archivo_id=archivo.id,
                usuario_id=usuario_actual.id,
                accion=AccionEnum.acceso,
                resultado="hashes SHA-1 y MD5 calculados",
            )
        )
        db.commit()
        db.refresh(archivo)
    return archivo


@router.post("/archivos/{archivo_id}/cotejar", response_model=CotejoOut)
def cotejar_hash(
    archivo_id: UUID,
    payload: CotejoIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Compara el hash del informe de una herramienta forense con la evidencia custodiada."""
    archivo = _archivo_listo(db, archivo_id, usuario_actual)
    db.refresh(archivo, with_for_update=True)  # dos cotejos a la vez no se pisan el historial
    resultado, alerta = cotejo_service.cotejar(
        db, archivo, usuario_actual, payload.herramienta, payload.texto, payload.referencia
    )
    db.add(
        LogCustodia(
            archivo_id=archivo.id,
            usuario_id=usuario_actual.id,
            accion=AccionEnum.verificacion,
            resultado=f"cotejo_{resultado['resultado']}",
        )
    )
    db.commit()
    if alerta:
        background_tasks.add_task(notificar_alerta, alerta.id)
    return resultado
@router.post("/archivos/{archivo_id}/virustotal")
def consultar_virustotal(
    archivo_id: UUID,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Consulta el SHA-256 de la evidencia en VirusTotal (solo el hash sale del sistema)."""
    archivo = _archivo_listo(db, archivo_id, usuario_actual)
    resultado = virustotal_service.consultar_hash(archivo.hash_original)
    db.add(
        LogCustodia(
            archivo_id=archivo.id,
            usuario_id=usuario_actual.id,
            accion=AccionEnum.verificacion,
            resultado=f"virustotal_{resultado['estado']}",
        )
    )
    db.commit()
    return resultado