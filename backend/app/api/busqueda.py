import re
import unicodedata

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.busqueda import BusquedaOut, ArchivoBusquedaOut
from app.schemas.caso import CasoOut
from app.models.caso import Caso
from app.models.archivo import Archivo
from app.core.security import get_current_user
from app.core.permisos import condicion_casos_visibles

router = APIRouter(tags=["busqueda"])


def _sin_tildes(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def fragmento(texto, q: str, contexto: int = 70):
    """Sprint 7 (historia 29): el pedazo del texto OCR donde aparece lo buscado (o su primera palabra)."""
    if not texto:
        return None
    plano = texto.replace("\f", " ")
    base = _sin_tildes(plano)  # NFKD+ascii conserva la longitud en español (á→a, ñ→n)
    if len(base) != len(plano):
        base = plano.lower()
    candidatos = [_sin_tildes(q)] + [p for p in re.findall(r"\w+", _sin_tildes(q)) if len(p) > 2]
    for c in candidatos:
        i = base.find(c)
        if i >= 0:
            ini, fin = max(0, i - contexto), min(len(plano), i + len(c) + contexto)
            trozo = " ".join(plano[ini:fin].split())
            return ("…" if ini else "") + trozo + ("…" if fin < len(plano) else "")
    return " ".join(plano[: contexto * 2].split()) + "…"


@router.get("/buscar", response_model=BusquedaOut)
def buscar(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Buscador instantáneo por número de caso o nombre de archivo
    (historia Sprint 2: 'quiero un buscador instantáneo por código o nombre
    de archivo, para encontrar un expediente de manera inmediata')."""
    patron = f"%{q}%"

    casos_query = db.query(Caso).filter(
        Caso.eliminado_en.is_(None), Caso.numero_caso.ilike(patron)
    )
    casos_query = casos_query.filter(condicion_casos_visibles(usuario_actual))
    casos = casos_query.order_by(Caso.creado_en.desc()).limit(10).all()

    # Sprint 7 (historia 29): también dentro del texto leído con OCR. Búsqueda de texto completo
    # en español (usa el índice GIN; "contratos" encuentra "contrato") o, para cifras y códigos
    # como "S/ 15,000" o "DNI 4512", coincidencia literal.
    # La expresión va literal, igual que en el índice ix_archivos_ocr_fts, para que Postgres lo use.
    en_texto = or_(
        text("to_tsvector('spanish', coalesce(archivos.ocr_texto, '')) @@ plainto_tsquery('spanish', :q)").bindparams(q=q),
        Archivo.ocr_texto.ilike(patron),
    )
    archivos_query = (
        db.query(Archivo, Caso)
        .join(Caso, Archivo.caso_id == Caso.id)
        .filter(Caso.eliminado_en.is_(None), or_(Archivo.nombre_original.ilike(patron), en_texto))
    )
    archivos_query = archivos_query.filter(condicion_casos_visibles(usuario_actual))
    filas = archivos_query.order_by(Archivo.subido_en.desc()).limit(10).all()

    archivos = [
        ArchivoBusquedaOut(
            id=archivo.id,
            caso_id=archivo.caso_id,
            nombre_original=archivo.nombre_original,
            hash_original=archivo.hash_original,
            hash_actual=archivo.hash_actual,
            metadatos=archivo.metadatos,
            estado_procesamiento=archivo.estado_procesamiento,
            subido_en=archivo.subido_en,
            caso_numero=caso.numero_caso,
            fragmento_texto=None if q.lower() in archivo.nombre_original.lower() else fragmento(archivo.ocr_texto, q),
        )
        for archivo, caso in filas
    ]

    return BusquedaOut(
        casos=[CasoOut.model_validate(c) for c in casos],
        archivos=archivos,
    )
