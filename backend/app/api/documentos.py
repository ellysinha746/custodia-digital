"""Sprint 7 (historias 29 y 31): texto de los documentos.

- H29: OCR de PDFs e imágenes (se ejecuta solo al subir; aquí se consulta o se vuelve a leer).
- H31: comparación del texto de dos versiones de un documento (cifras y palabras cambiadas).
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.archivos import _obtener_archivo
from app.core.permisos import exigir
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.archivo import EstadoProcesamientoEnum
from app.models.log_custodia import LogCustodia, AccionEnum
from app.models.version_observada import VersionObservada
from app.schemas.archivo import ArchivoOut
from app.services import ocr_service, comparacion_service

router = APIRouter(tags=["documentos (OCR)"])


class OcrOut(BaseModel):
    estado: Optional[str] = None
    paginas: List[str] = []          # texto de cada página
    confianza: Optional[float] = None
    motor: Optional[str] = None
    leido_en: Optional[datetime] = None
    error: Optional[str] = None


@router.get("/archivos/{archivo_id}/ocr", response_model=OcrOut)
def ver_texto(archivo_id: UUID, db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    """Texto extraído del documento, página por página."""
    a = _obtener_archivo(db, archivo_id, usuario_actual)
    return OcrOut(
        estado=a.ocr_estado,
        paginas=a.ocr_texto.split("\f") if a.ocr_texto else [],
        confianza=a.ocr_confianza,
        motor=a.ocr_motor,
        leido_en=a.ocr_en,
        error=a.ocr_error,
    )


@router.post("/archivos/{archivo_id}/ocr", response_model=ArchivoOut, status_code=202)
def leer_texto(
    archivo_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """(Re)lee el texto con OCR en segundo plano: evidencia anterior al Sprint 7 o un OCR que falló."""
    exigir(usuario_actual, "verificar_integridad")
    archivo = _obtener_archivo(db, archivo_id, usuario_actual)
    if archivo.estado_procesamiento != EstadoProcesamientoEnum.listo:
        raise HTTPException(status_code=409, detail="El archivo aún se está procesando.")
    if archivo.ocr_estado in ("pendiente", "procesando"):
        raise HTTPException(status_code=409, detail="El texto de este documento ya se está leyendo.")
    if not ocr_service.preparar(archivo):
        raise HTTPException(status_code=415, detail="Solo se puede leer el texto de imágenes y PDFs.")
    db.commit()
    db.refresh(archivo)
    background_tasks.add_task(ocr_service.procesar, archivo.id, usuario_actual.id)
    return archivo


# ---------------------------------------------------------------------------
# Sprint 7 (historia 31): cotejo de texto entre versiones.

class CompararIn(BaseModel):
    contra_archivo_id: Optional[UUID] = None   # otro documento del mismo caso
    contra_version_id: Optional[UUID] = None   # o una versión observada (perito de parte)


class LadoOut(BaseModel):
    nombre: str
    tipo: str                 # archivo | version_observada
    motor: Optional[str] = None
    confianza: Optional[float] = None


class ComparacionOut(BaseModel):
    a: LadoOut
    b: LadoOut
    similitud: float
    cambios: int
    palabras_a: int
    palabras_b: int
    cifras_cambiadas: List[dict]
    segmentos: List[dict]


def _texto_listo(archivo) -> str:
    if archivo.ocr_estado != "listo" or not archivo.ocr_texto:
        raise HTTPException(
            status_code=409,
            detail=f"Primero hay que leer el texto (OCR) de «{archivo.nombre_original}».",
        )
    return archivo.ocr_texto


@router.post("/archivos/{archivo_id}/comparar-texto", response_model=ComparacionOut)
def comparar_texto(
    archivo_id: UUID,
    payload: CompararIn,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Compara el texto del documento con otro del caso o con una versión observada."""
    if (payload.contra_archivo_id is None) == (payload.contra_version_id is None):
        raise HTTPException(status_code=400, detail="Elige UN documento o UNA versión observada para comparar.")
    a = _obtener_archivo(db, archivo_id, usuario_actual)
    texto_a = _texto_listo(a)

    if payload.contra_archivo_id:
        b = _obtener_archivo(db, payload.contra_archivo_id, usuario_actual)
        if b.caso_id != a.caso_id:
            raise HTTPException(status_code=400, detail="Solo se comparan documentos del mismo caso.")
        if b.id == a.id:
            raise HTTPException(status_code=400, detail="Elige un documento distinto.")
        texto_b = _texto_listo(b)
        lado_b = LadoOut(nombre=b.nombre_original, tipo="archivo", motor=b.ocr_motor, confianza=b.ocr_confianza)
    else:
        v = db.query(VersionObservada).filter(VersionObservada.id == payload.contra_version_id).first()
        if not v or _obtener_archivo(db, v.archivo_id, usuario_actual).caso_id != a.caso_id:
            raise HTTPException(status_code=404, detail="Versión observada no encontrada en este caso.")
        try:
            r = ocr_service.leer_texto_de(v.ruta)  # se lee en el momento: las versiones no tienen OCR guardado
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"No se pudo leer el texto de la versión observada: {e}")
        texto_b = r["texto"]
        if not texto_b.replace("\f", "").strip():
            raise HTTPException(status_code=422, detail="La versión observada no tiene texto legible.")
        lado_b = LadoOut(nombre=v.nombre, tipo="version_observada", motor=r["motor"], confianza=r["confianza"])

    resultado = comparacion_service.comparar(texto_a, texto_b)
    db.add(LogCustodia(
        archivo_id=a.id, usuario_id=usuario_actual.id, accion=AccionEnum.acceso,
        resultado=(f"comparación de texto con «{lado_b.nombre}»: {resultado['cambios']} cambio(s), "
                   f"{len(resultado['cifras_cambiadas'])} con cifras, similitud {resultado['similitud']:.0f}%")[:250],
    ))
    db.commit()
    return ComparacionOut(
        a=LadoOut(nombre=a.nombre_original, tipo="archivo", motor=a.ocr_motor, confianza=a.ocr_confianza),
        b=lado_b,
        **resultado,
    )
