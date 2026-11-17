"""Sprint 7 (historia 34): borrador descriptivo asistido por IA — generar, revisar y firmar."""
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.archivos import _obtener_caso, _obtener_caso_editable
from app.api.grafotecnia import _caso_de_grafotecnia
from app.core import sello
from app.core.config import settings
from app.core.permisos import exigir
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.borrador_ia import BorradorIA
from app.models.usuario import RolEnum
from app.services import ia_service
from app.services.acta_juramento_service import normalizar_nombre

router = APIRouter(tags=["borrador asistido por IA"])


class EstadoIAOut(BaseModel):
    habilitada: bool
    proveedor: str
    modelo: str


class BorradorOut(BaseModel):
    id: UUID
    caso_id: UUID
    estado: str
    texto: str
    editado: bool                       # el perito cambió el texto de la IA
    generado_por_id: UUID
    generado_por: str
    generado_en: datetime
    modelo_solicitado: str
    modelo_respondio: Optional[str] = None
    documentos: List[Dict[str, Any]]
    enviado: Dict[str, Any]
    tokens_entrada: Optional[int] = None
    tokens_salida: Optional[int] = None
    firmado_por: Optional[str] = None
    firmado_en: Optional[datetime] = None
    hash_texto: Optional[str] = None
    integro: Optional[bool] = None      # solo firmados: el texto no cambió desde la firma


class TextoIn(BaseModel):
    texto: str = Field(..., min_length=20, max_length=100_000)


class FirmaIn(BaseModel):
    firma: str = Field(..., min_length=3)   # nombre completo, como en el juramento
    revisado: bool                          # declara que revisó y corrigió el borrador


def _mensaje_firma(b: BorradorIA) -> bytes:
    return f"{b.id}|{b.hash_texto}|{b.firmado_por_id}|{b.firmado_en.astimezone(timezone.utc).isoformat()}".encode()


def _integro(b: BorradorIA) -> Optional[bool]:
    if b.estado != "firmado":
        return None
    return hashlib.sha256(b.texto.encode()).hexdigest() == b.hash_texto and sello.firma_valida(_mensaje_firma(b), b.firma_hmac)


def _salida(b: BorradorIA) -> BorradorOut:
    return BorradorOut(
        id=b.id, caso_id=b.caso_id, estado=b.estado, texto=b.texto, editado=b.texto != b.texto_generado,
        generado_por_id=b.generado_por_id, generado_por=b.generado_por.nombre, generado_en=b.generado_en,
        modelo_solicitado=b.modelo_solicitado, modelo_respondio=b.modelo_respondio,
        documentos=b.documentos, enviado=b.enviado, tokens_entrada=b.tokens_entrada, tokens_salida=b.tokens_salida,
        firmado_por=b.firmado_por.nombre if b.firmado_por else None, firmado_en=b.firmado_en,
        hash_texto=b.hash_texto, integro=_integro(b),
    )


def _borrador(db: Session, borrador_id: UUID, usuario) -> BorradorIA:
    b = db.query(BorradorIA).filter(BorradorIA.id == borrador_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Borrador no encontrado.")
    _obtener_caso(db, b.caso_id, usuario)  # hereda la visibilidad del caso
    return b


def _borrador_propio(db: Session, borrador_id: UUID, usuario) -> BorradorIA:
    b = _borrador(db, borrador_id, usuario)
    if b.generado_por_id != usuario.id and usuario.rol != RolEnum.admin:
        raise HTTPException(status_code=403, detail="Solo el perito que generó el borrador puede revisarlo y firmarlo.")
    if b.estado == "firmado":
        raise HTTPException(status_code=409, detail="El borrador ya está firmado: no se puede modificar.")
    return b


@router.get("/ia/estado", response_model=EstadoIAOut)
def estado_ia(usuario_actual=Depends(get_current_user)):
    return EstadoIAOut(habilitada=ia_service.habilitada(), proveedor=ia_service.PROVEEDOR, modelo=settings.IA_MODELO)


@router.post("/casos/{caso_id}/borradores-ia", response_model=BorradorOut, status_code=201)
def generar_borrador(caso_id: UUID, db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    """Redacta un borrador descriptivo con IA a partir de los documentos dubitados e indubitados."""
    exigir(usuario_actual, "editar_metadatos")
    caso = _obtener_caso_editable(db, caso_id, usuario_actual)
    _caso_de_grafotecnia(caso)
    return _salida(ia_service.generar(db, caso, usuario_actual))


@router.get("/casos/{caso_id}/borradores-ia", response_model=List[BorradorOut])
def listar_borradores(caso_id: UUID, db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    _obtener_caso(db, caso_id, usuario_actual)
    filas = db.query(BorradorIA).filter(BorradorIA.caso_id == caso_id).order_by(BorradorIA.generado_en.desc()).all()
    return [_salida(b) for b in filas]


@router.patch("/borradores-ia/{borrador_id}", response_model=BorradorOut)
def revisar_borrador(borrador_id: UUID, payload: TextoIn, db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    """El perito corrige el texto (el original de la IA se conserva aparte)."""
    b = _borrador_propio(db, borrador_id, usuario_actual)
    b.texto = payload.texto
    db.commit()
    db.refresh(b)
    return _salida(b)


@router.post("/borradores-ia/{borrador_id}/firmar", response_model=BorradorOut)
def firmar_borrador(borrador_id: UUID, payload: FirmaIn, db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    """El perito declara que lo revisó y lo firma con su nombre: queda inmutable y sellado."""
    b = _borrador_propio(db, borrador_id, usuario_actual)
    if not payload.revisado:
        raise HTTPException(status_code=400, detail="Debes declarar que revisaste el borrador antes de firmarlo.")
    if normalizar_nombre(payload.firma) != normalizar_nombre(usuario_actual.nombre):
        raise HTTPException(status_code=400, detail=f"Escribe tu nombre completo tal como está registrado: {usuario_actual.nombre}.")
    b.estado = "firmado"
    b.firmado_por_id = usuario_actual.id
    b.firmado_en = datetime.now(timezone.utc)
    b.hash_texto = hashlib.sha256(b.texto.encode()).hexdigest()
    b.firma_hmac = sello.firmar(_mensaje_firma(b))
    db.commit()
    db.refresh(b)
    return _salida(b)


@router.get("/borradores-ia/{borrador_id}/descargar")
def descargar_borrador(borrador_id: UUID, db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    """Texto del borrador con su constancia: modelo, fecha, qué se envió y la firma del perito."""
    b = _borrador(db, borrador_id, usuario_actual)
    docs = "\n".join(f"  {d['etiqueta']} {d['rol']:<10} {d['nombre']}  SHA-256 {d['sha256']}" for d in b.documentos)
    if b.estado == "firmado":
        firma = (f"Revisado y firmado por: {b.firmado_por.nombre} el {b.firmado_en:%d/%m/%Y %H:%M} UTC\n"
                 f"SHA-256 del texto: {b.hash_texto}\nIntegridad: {'VERIFICADA' if _integro(b) else 'NO COINCIDE'}")
    else:
        firma = "ESTADO: BORRADOR SIN FIRMAR — pendiente de revisión del perito."
    constancia = (
        "\n\n" + "=" * 72 + "\nCONSTANCIA (CustodiaDigital)\n"
        f"Generado por IA: {b.modelo_respondio or b.modelo_solicitado} ({b.enviado.get('proveedor')}) "
        f"el {b.generado_en:%d/%m/%Y %H:%M} UTC, a pedido de {b.generado_por.nombre}\n"
        f"Enviado al proveedor: {b.enviado.get('imagenes', 0)} imagen(es), {b.enviado.get('textos_ocr', 0)} texto(s) OCR, "
        f"{b.enviado.get('metricas', 0)} conjunto(s) de métricas\n"
        f"Documentos:\n{docs}\n"
        f"Texto modificado por el perito respecto de la IA: {'sí' if b.texto != b.texto_generado else 'no'}\n{firma}\n"
    )
    return Response(
        content=(b.texto + constancia).encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="borrador_ia_{str(b.id)[:8]}.txt"'},
    )
