from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.permisos import requiere
from app.db.session import get_db
from app.models.pericia import RecordatorioPlazo
from app.services.recordatorio_service import TITULOS, enviar_recordatorios, plazos_por_vencer

# Sprint 6 (historia 26): recordatorio de plazos por vencer.
router = APIRouter(prefix="/recordatorios-plazo", tags=["recordatorios de plazo"])


class PlazoOut(BaseModel):
    pericia_id: UUID
    pericia_codigo: str
    caso_numero: str
    tipo: str
    tipo_etiqueta: str
    vence_en: datetime
    recordado_en: Optional[datetime] = None
    destinatarios: List[str] = []


class EnvioOut(BaseModel):
    enviados: int


@router.get("", response_model=List[PlazoOut])
def listar(db: Session = Depends(get_db), usuario_actual=Depends(requiere("gestionar_pericias"))):
    """Plazos que vencen pronto (con o sin recordatorio) y los últimos recordatorios enviados."""
    salida = {}
    for item in plazos_por_vencer(db):
        p = item["pericia"]
        salida[(p.id, item["tipo"], item["vence_en"])] = PlazoOut(
            pericia_id=p.id, pericia_codigo=p.codigo, caso_numero=p.caso.numero_caso,
            tipo=item["tipo"], tipo_etiqueta=TITULOS[item["tipo"]], vence_en=item["vence_en"],
        )
    for r in db.query(RecordatorioPlazo).order_by(RecordatorioPlazo.enviado_en.desc()).limit(20).all():
        clave = (r.pericia_id, r.tipo, r.vence_en)
        fila = salida.get(clave) or PlazoOut(
            pericia_id=r.pericia_id, pericia_codigo=r.pericia.codigo, caso_numero=r.pericia.caso.numero_caso,
            tipo=r.tipo, tipo_etiqueta=TITULOS.get(r.tipo, r.tipo), vence_en=r.vence_en,
        )
        fila.recordado_en = r.enviado_en
        fila.destinatarios = r.destinatarios or []
        salida[clave] = fila
    return sorted(salida.values(), key=lambda f: f.vence_en)


@router.post("/enviar", response_model=EnvioOut)
def enviar_ahora(usuario_actual=Depends(requiere("gestionar_pericias"))):
    """Revisa los plazos en este momento (además de la revisión automática)."""
    return EnvioOut(enviados=enviar_recordatorios())