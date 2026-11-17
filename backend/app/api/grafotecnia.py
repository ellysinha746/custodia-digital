"""Sprint 7 (historia 28): especialidad grafotecnia.

- Cada documento del caso se marca como DUBITADO (el cuestionado: la firma o el texto cuya
  autoría se discute) o INDUBITADO (de autoría conocida, sirve de patrón de comparación).
- Las páginas se ven como imagen para el cotejo lado a lado con zoom (se lee la copia de trabajo).
"""
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.archivos import _obtener_archivo, _obtener_caso_editable
from app.core.permisos import exigir
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.log_custodia import LogCustodia, AccionEnum
from app.models.usuario import EspecialidadEnum
from app.schemas.archivo import ArchivoOut
from app.services import vista_service
from app.services.storage_service import existe

router = APIRouter(tags=["grafotecnia"])

ETIQUETA_ROL = {"dubitado": "dubitado (cuestionado)", "indubitado": "indubitado (patrón)"}


class RolGrafotecnicoIn(BaseModel):
    rol: Optional[Literal["dubitado", "indubitado"]] = None  # None = quitar la marca


def _caso_de_grafotecnia(caso) -> None:
    especialidades = caso.especialidades or [caso.especialidad.value]
    if EspecialidadEnum.grafotecnia.value not in especialidades:
        raise HTTPException(
            status_code=409,
            detail="Solo los casos de grafotecnia clasifican documentos como dubitados o indubitados.",
        )


@router.patch("/archivos/{archivo_id}/grafotecnia", response_model=ArchivoOut)
def marcar_rol_grafotecnico(
    archivo_id: UUID,
    payload: RolGrafotecnicoIn,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    exigir(usuario_actual, "editar_metadatos")
    archivo = _obtener_archivo(db, archivo_id, usuario_actual)
    caso = _obtener_caso_editable(db, archivo.caso_id, usuario_actual)
    _caso_de_grafotecnia(caso)
    if archivo.rol_grafotecnico == payload.rol:
        return archivo
    anterior = archivo.rol_grafotecnico
    archivo.rol_grafotecnico = payload.rol
    detalle = (
        f"grafotecnia: marcado como {ETIQUETA_ROL[payload.rol]}" if payload.rol
        else f"grafotecnia: se quitó la marca de {anterior}"
    )
    db.add(LogCustodia(archivo_id=archivo.id, usuario_id=usuario_actual.id, accion=AccionEnum.acceso, resultado=detalle))
    db.commit()
    db.refresh(archivo)
    return archivo


@router.get("/archivos/{archivo_id}/vista")
def ver_pagina(
    archivo_id: UUID,
    pagina: int = Query(1, ge=1, le=5000),
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Una página del documento como PNG (para el cotejo con zoom). Queda en la cadena de custodia."""
    archivo = _obtener_archivo(db, archivo_id, usuario_actual)
    if not existe(archivo.ruta_copia_trabajo):
        raise HTTPException(status_code=404, detail="La copia de trabajo ya no está en el almacenamiento.")
    png, total = vista_service.png_de_pagina(archivo, pagina)
    db.add(LogCustodia(
        archivo_id=archivo.id, usuario_id=usuario_actual.id, accion=AccionEnum.acceso,
        resultado=f"vista para cotejo (página {pagina} de {total})",
    ))
    db.commit()
    return Response(
        content=png,
        media_type="image/png",
        headers={"X-Paginas": str(total), "Access-Control-Expose-Headers": "X-Paginas"},
    )
