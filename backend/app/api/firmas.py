"""Sprint 7 (historia 30): análisis comparativo de firmas con OpenCV.

El perito elige UNA firma dubitada y DOS o más indubitadas (patrones) del caso, cada una con
su página y, si quiere, un recorte. Se mide cuánto varían los patrones entre sí (la variación
natural del autor) y si la dubitada cae dentro de esa variación. Apoya al perito: no dictamina.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.archivos import _obtener_archivo, _obtener_caso, _obtener_caso_editable
from app.api.grafotecnia import _caso_de_grafotecnia
from app.core.permisos import exigir
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.analisis_firma import AnalisisFirma
from app.models.archivo import Archivo
from app.models.log_custodia import LogCustodia, AccionEnum
from app.services import firma_service, ubicacion_firma_service, vista_service
from app.services.storage_service import existe

router = APIRouter(tags=["análisis de firmas"])

MAX_INDUBITADAS = 8


class RecorteIn(BaseModel):
    x: float = Field(..., ge=0, le=1)
    y: float = Field(..., ge=0, le=1)
    ancho: float = Field(..., gt=0, le=1)
    alto: float = Field(..., gt=0, le=1)


class FirmaIn(BaseModel):
    archivo_id: UUID
    pagina: int = Field(1, ge=1, le=5000)
    recorte: Optional[RecorteIn] = None   # sin recorte = página completa


class AnalisisIn(BaseModel):
    dubitada: FirmaIn
    indubitadas: List[FirmaIn] = Field(..., min_length=2, max_length=MAX_INDUBITADAS)


class AnalisisOut(BaseModel):
    id: UUID
    caso_id: UUID
    realizado_por: str
    realizado_en: datetime
    entradas: List[Dict[str, Any]]
    resultado: Dict[str, Any]
    hash_resultado: str
    integro: bool


def _salida(a: AnalisisFirma) -> AnalisisOut:
    return AnalisisOut(
        id=a.id, caso_id=a.caso_id, realizado_por=a.realizado_por.nombre, realizado_en=a.realizado_en,
        entradas=a.entradas, resultado=a.resultado, hash_resultado=a.hash_resultado,
        integro=firma_service.hash_resultado(a.resultado) == a.hash_resultado,
    )


def _cargar_firma(db: Session, caso_id: UUID, entrada: FirmaIn, rol_esperado: str) -> tuple:
    archivo = db.query(Archivo).filter(Archivo.id == entrada.archivo_id, Archivo.caso_id == caso_id).first()
    if not archivo:
        raise HTTPException(status_code=404, detail="Uno de los archivos elegidos no pertenece a este caso.")
    if archivo.rol_grafotecnico != rol_esperado:
        raise HTTPException(
            status_code=400,
            detail=f"«{archivo.nombre_original}» no está marcado como {rol_esperado}.",
        )
    tipo = vista_service.tipo_visual(archivo)
    if not tipo:
        raise HTTPException(status_code=415, detail=f"«{archivo.nombre_original}» no es una imagen ni un PDF.")
    if not existe(archivo.ruta_copia_trabajo):
        raise HTTPException(status_code=404, detail=f"La copia de trabajo de «{archivo.nombre_original}» ya no está en el almacenamiento.")
    recorte = entrada.recorte.model_dump() if entrada.recorte else None
    with vista_service.copia_local(archivo.ruta_copia_trabajo) as ruta:
        imagen, _ = vista_service.imagen_de_pagina(ruta, tipo, entrada.pagina, dpi=200)
    try:
        firma = firma_service.preparar(firma_service.recortar(imagen, recorte))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"«{archivo.nombre_original}»: {e}")
    datos = {
        "archivo_id": str(archivo.id), "rol": rol_esperado, "nombre": archivo.nombre_original,
        "sha256": archivo.hash_actual, "pagina": entrada.pagina, "recorte": recorte,
    }
    return archivo, {"id": str(archivo.id), "nombre": archivo.nombre_original, "firma": firma}, datos


@router.post("/casos/{caso_id}/firmas/analisis", response_model=AnalisisOut, status_code=201)
def analizar_firmas(caso_id: UUID, payload: AnalisisIn, db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    """Compara la firma dubitada con los patrones indubitados y guarda el resultado."""
    exigir(usuario_actual, "editar_metadatos")
    caso = _obtener_caso_editable(db, caso_id, usuario_actual)
    _caso_de_grafotecnia(caso)
    ids = [payload.dubitada.archivo_id] + [x.archivo_id for x in payload.indubitadas]
    if len(set((x.archivo_id, x.pagina) for x in [payload.dubitada] + payload.indubitadas)) != len(ids):
        raise HTTPException(status_code=400, detail="Elegiste la misma firma (archivo y página) más de una vez.")

    archivo_dub, dubitada, entrada_dub = _cargar_firma(db, caso_id, payload.dubitada, "dubitado")
    patrones, entradas, archivos = [], [entrada_dub], [archivo_dub]
    for x in payload.indubitadas:
        archivo, firma, entrada = _cargar_firma(db, caso_id, x, "indubitado")
        patrones.append(firma)
        entradas.append(entrada)
        archivos.append(archivo)

    resultado = firma_service.analizar(dubitada, patrones)
    analisis = AnalisisFirma(
        caso_id=caso.id, realizado_por_id=usuario_actual.id, realizado_en=datetime.now(timezone.utc),
        dubitada_id=archivo_dub.id, entradas=entradas, resultado=resultado,
        hash_resultado=firma_service.hash_resultado(resultado),
    )
    db.add(analisis)
    for archivo in {a.id: a for a in archivos}.values():
        db.add(LogCustodia(
            archivo_id=archivo.id, usuario_id=usuario_actual.id, accion=AccionEnum.acceso,
            resultado=f"análisis de firmas ({firma_service.MOTOR})",
        ))
    db.commit()
    db.refresh(analisis)
    return _salida(analisis)


@router.get("/casos/{caso_id}/firmas/analisis", response_model=List[AnalisisOut])
def listar_analisis(caso_id: UUID, db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    _obtener_caso(db, caso_id, usuario_actual)
    filas = db.query(AnalisisFirma).filter(AnalisisFirma.caso_id == caso_id).order_by(AnalisisFirma.realizado_en.desc()).all()
    return [_salida(a) for a in filas]


# Sprint 8 (historia 41): ubicar firmas automáticamente en una página.
@router.get("/archivos/{archivo_id}/firmas/ubicar")
def ubicar_firmas(
    archivo_id: UUID,
    pagina: int = Query(1, ge=1, le=5000),
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Sugiere las zonas de la página donde parece haber una firma (el perito confirma)."""
    archivo = _obtener_archivo(db, archivo_id, usuario_actual)
    tipo = vista_service.tipo_visual(archivo)
    if not tipo:
        raise HTTPException(status_code=415, detail="Este archivo no es una imagen ni un PDF.")
    if not existe(archivo.ruta_copia_trabajo):
        raise HTTPException(status_code=404, detail="La copia de trabajo ya no está en el almacenamiento.")
    with vista_service.copia_local(archivo.ruta_copia_trabajo) as ruta:
        imagen, total = vista_service.imagen_de_pagina(ruta, tipo, pagina, dpi=200)
    resultado = ubicacion_firma_service.detectar(imagen)
    db.add(LogCustodia(
        archivo_id=archivo.id, usuario_id=usuario_actual.id, accion=AccionEnum.acceso,
        resultado=f"ubicación automática de firmas (página {pagina} de {total}): {len(resultado['candidatos'])} zona(s)",
    ))
    db.commit()
    return {"pagina": pagina, "paginas": total, **resultado}
