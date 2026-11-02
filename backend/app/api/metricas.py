from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.alerta import Alerta
from app.models.archivo import Archivo
from app.models.caso import Caso, EstadoCasoEnum
from app.models.log_custodia import LogCustodia, AccionEnum
from app.models.usuario import RolEnum

router = APIRouter(prefix="/metricas", tags=["dashboard"])

DIAS_ACTIVIDAD = 14


class ActividadDia(BaseModel):
    fecha: str  # YYYY-MM-DD (hora de Lima)
    eventos: int
    alertas: int


class MetricasOut(BaseModel):
    casos_total: int
    casos_abiertos: int
    casos_en_proceso: int
    casos_cerrados: int
    casos_en_papelera: int
    casos_por_especialidad: Dict[str, int]
    archivos_total: int
    verificaciones_total: int
    alertas_total: int
    alertas_pendientes: int
    alertas_atendidas: int
    alertas_por_tipo: Dict[str, int]
    tiempo_promedio_cierre_horas: Optional[float] = None
    casos_cierre_medido: int
    actividad: List[ActividadDia]
    generado_en: datetime


@router.get("", response_model=MetricasOut)
def obtener_metricas(
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Historia 18: métricas generales del sistema (solo administrador)."""
    if usuario_actual.rol != RolEnum.admin:
        raise HTTPException(status_code=403, detail="Solo un administrador puede ver el dashboard.")

    vivos = db.query(Caso).filter(Caso.eliminado_en.is_(None))
    por_estado = dict(
        db.query(Caso.estado, func.count()).filter(Caso.eliminado_en.is_(None)).group_by(Caso.estado).all()
    )
    por_especialidad = {
        esp.value: n
        for esp, n in db.query(Caso.especialidad, func.count())
        .filter(Caso.eliminado_en.is_(None))
        .group_by(Caso.especialidad)
        .all()
    }

    # Tiempo promedio de cierre: solo casos cerrados que tienen fecha de cierre registrada.
    cerrados = vivos.filter(Caso.estado == EstadoCasoEnum.cerrado, Caso.cerrado_en.isnot(None)).all()
    horas = [(c.cerrado_en - c.creado_en).total_seconds() / 3600 for c in cerrados]
    promedio = round(sum(horas) / len(horas), 1) if horas else None

    alertas_por_tipo = dict(db.query(Alerta.tipo, func.count()).group_by(Alerta.tipo).all())
    alertas_total = sum(alertas_por_tipo.values())
    pendientes = db.query(Alerta).filter(Alerta.atendida_en.is_(None)).count()

    # Actividad de los últimos 14 días, agrupada por día en hora de Lima.
    zona = timezone(timedelta(hours=-5))
    hoy = datetime.now(zona).date()
    desde = datetime.combine(hoy - timedelta(days=DIAS_ACTIVIDAD - 1), datetime.min.time(), zona)
    conteo_eventos: Dict[str, int] = {}
    for (fecha,) in db.query(LogCustodia.fecha).filter(LogCustodia.fecha >= desde).all():
        clave = fecha.astimezone(zona).date().isoformat()
        conteo_eventos[clave] = conteo_eventos.get(clave, 0) + 1
    conteo_alertas: Dict[str, int] = {}
    for (fecha,) in db.query(Alerta.creada_en).filter(Alerta.creada_en >= desde).all():
        clave = fecha.astimezone(zona).date().isoformat()
        conteo_alertas[clave] = conteo_alertas.get(clave, 0) + 1
    actividad = []
    for i in range(DIAS_ACTIVIDAD):
        dia = (hoy - timedelta(days=DIAS_ACTIVIDAD - 1 - i)).isoformat()
        actividad.append(
            ActividadDia(fecha=dia, eventos=conteo_eventos.get(dia, 0), alertas=conteo_alertas.get(dia, 0))
        )

    return MetricasOut(
        casos_total=vivos.count(),
        casos_abiertos=por_estado.get(EstadoCasoEnum.abierto, 0),
        casos_en_proceso=por_estado.get(EstadoCasoEnum.en_proceso, 0),
        casos_cerrados=por_estado.get(EstadoCasoEnum.cerrado, 0),
        casos_en_papelera=db.query(Caso).filter(Caso.eliminado_en.isnot(None)).count(),
        casos_por_especialidad=por_especialidad,
        archivos_total=db.query(Archivo).join(Caso).filter(Caso.eliminado_en.is_(None)).count(),
        verificaciones_total=db.query(LogCustodia).filter(LogCustodia.accion == AccionEnum.verificacion).count(),
        alertas_total=alertas_total,
        alertas_pendientes=pendientes,
        alertas_atendidas=alertas_total - pendientes,
        alertas_por_tipo=alertas_por_tipo,
        tiempo_promedio_cierre_horas=promedio,
        casos_cierre_medido=len(horas),
        actividad=actividad,
        generado_en=datetime.now(timezone.utc),
    )