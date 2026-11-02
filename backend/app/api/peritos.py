from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.core.permisos import exigir, puede, ETIQUETAS_ROL
from app.models.pericia import Pericia, DesignacionPericia
from app.models.usuario import Usuario, RolEnum, EspecialidadEnum
from app.services import pericia_service as reglas
from app.api.pericias import MOTIVOS_SUBROGACION

# Sprint 5: historia 19.2 (padrón de peritos) y 19.9 (perfil del perito).
router = APIRouter(tags=["padrón de peritos"])

ROLES_PERITO = (RolEnum.perito, RolEnum.perito_parte)


class PeritoOut(BaseModel):
    id: UUID
    nombre: str
    email: str
    tipo: str  # perito | perito_parte
    tipo_etiqueta: str
    especialidad: EspecialidadEnum
    institucion: Optional[str] = None
    registro_profesional: Optional[str] = None
    telefono: Optional[str] = None
    habilitado: bool
    pericias_activas: int


class PericiaResumen(BaseModel):
    id: UUID
    codigo: str
    caso_id: UUID
    caso_numero: str
    estado: str
    estado_etiqueta: str
    rol_en_pericia: str  # oficial | parte
    fecha_limite: datetime
    traslado_vence_en: Optional[datetime] = None
    observaciones_pendientes: int
    alerta: Optional[str] = None


class SubrogacionResumen(BaseModel):
    codigo: str
    caso_id: UUID
    caso_numero: str
    subrogado_en: datetime
    motivo: Optional[str] = None
    documento: Optional[str] = None


class PerfilOut(BaseModel):
    perito: PeritoOut
    pericias_por_estado: Dict[str, int]
    pericias: List[PericiaResumen]
    por_absolver: List[PericiaResumen]
    por_observar: List[PericiaResumen]
    plazos_por_vencer: List[PericiaResumen]
    subrogaciones: List[SubrogacionResumen]


def _activas_por_perito(db: Session) -> dict:
    filas = (
        db.query(DesignacionPericia.usuario_id, Pericia.id)
        .join(Pericia, DesignacionPericia.pericia_id == Pericia.id)
        .filter(DesignacionPericia.activa.is_(True), Pericia.estado != "concluida")
        .all()
    )
    conteo: dict = {}
    for usuario_id, _ in filas:
        conteo[usuario_id] = conteo.get(usuario_id, 0) + 1
    return conteo


def _perito_out(u: Usuario, activas: int) -> PeritoOut:
    return PeritoOut(
        id=u.id,
        nombre=u.nombre,
        email=u.email,
        tipo=u.rol.value,
        tipo_etiqueta=ETIQUETAS_ROL.get(u.rol, u.rol.value),
        especialidad=u.especialidad,
        institucion=u.institucion,
        registro_profesional=u.registro_profesional,
        telefono=u.telefono,
        habilitado=u.activo,
        pericias_activas=activas,
    )


@router.get("/peritos", response_model=List[PeritoOut])
def padron_de_peritos(
    tipo: Optional[str] = Query(None, pattern="^(perito|perito_parte)$"),
    especialidad: Optional[EspecialidadEnum] = None,
    q: Optional[str] = None,
    solo_habilitados: bool = False,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Historia 19.2: padrón de peritos oficiales y de parte, con filtros."""
    exigir(usuario_actual, "ver_padron")
    query = db.query(Usuario).filter(Usuario.rol.in_(ROLES_PERITO))
    if tipo:
        query = query.filter(Usuario.rol == RolEnum(tipo))
    if especialidad:
        query = query.filter(Usuario.especialidad == especialidad)
    if solo_habilitados:
        query = query.filter(Usuario.activo.is_(True))
    if q and q.strip():
        patron = f"%{q.strip()}%"
        query = query.filter(
            or_(Usuario.nombre.ilike(patron), Usuario.institucion.ilike(patron), Usuario.registro_profesional.ilike(patron))
        )
    activas = _activas_por_perito(db)
    return [_perito_out(u, activas.get(u.id, 0)) for u in query.order_by(Usuario.rol, Usuario.nombre).all()]


def _perfil(db: Session, perito: Usuario) -> PerfilOut:
    designaciones = (
        db.query(DesignacionPericia)
        .filter(DesignacionPericia.usuario_id == perito.id)
        .order_by(DesignacionPericia.designado_en.desc())
        .all()
    )
    pronto = reglas.ahora() + timedelta(days=3)
    pericias: List[PericiaResumen] = []
    por_estado: Dict[str, int] = {}
    vistas = set()
    for d in designaciones:
        p = d.pericia
        if not d.activa or p.id in vistas:
            continue
        vistas.add(p.id)
        pendientes = sum(1 for o in p.observaciones if not o.respuesta)
        alerta = None
        if p.estado == "designada" and p.fecha_limite <= pronto:
            alerta = "Plazo de la pericia vencido" if p.fecha_limite < reglas.ahora() else "Plazo de la pericia por vencer"
        elif p.estado in ("en_traslado", "observada") and p.traslado_vence_en and p.traslado_vence_en <= pronto and d.tipo == "parte":
            alerta = "Traslado vencido" if reglas.traslado_vencido(p) else "Traslado por vencer"
        pericias.append(
            PericiaResumen(
                id=p.id, codigo=p.codigo, caso_id=p.caso_id, caso_numero=p.caso.numero_caso,
                estado=p.estado, estado_etiqueta=reglas.etiqueta_estado(p.estado), rol_en_pericia=d.tipo,
                fecha_limite=p.fecha_limite, traslado_vence_en=p.traslado_vence_en,
                observaciones_pendientes=pendientes, alerta=alerta,
            )
        )
        etiqueta = reglas.etiqueta_estado(p.estado)
        por_estado[etiqueta] = por_estado.get(etiqueta, 0) + 1

    subrogaciones = [
        SubrogacionResumen(
            codigo=d.pericia.codigo, caso_id=d.pericia.caso_id, caso_numero=d.pericia.caso.numero_caso,
            subrogado_en=d.subrogado_en, motivo=MOTIVOS_SUBROGACION.get(d.motivo_subrogacion, d.motivo_subrogacion), documento=d.documento_subrogacion,
        )
        for d in designaciones
        if not d.activa and d.subrogado_en
    ]
    return PerfilOut(
        perito=_perito_out(perito, sum(1 for p in pericias if p.estado != "concluida")),
        pericias_por_estado=por_estado,
        pericias=pericias,
        por_absolver=[p for p in pericias if p.rol_en_pericia == "oficial" and p.estado == "en_absolucion"],
        por_observar=[p for p in pericias if p.rol_en_pericia == "parte" and p.estado in ("en_traslado", "observada")],
        plazos_por_vencer=[p for p in pericias if p.alerta],
        subrogaciones=subrogaciones,
    )


@router.get("/perfil", response_model=PerfilOut)
def mi_perfil(db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    """Historia 19.9: el perito ve su carga de trabajo."""
    if usuario_actual.rol not in ROLES_PERITO:
        raise HTTPException(status_code=400, detail="El perfil pericial es solo para peritos.")
    return _perfil(db, usuario_actual)


@router.get("/peritos/{perito_id}/perfil", response_model=PerfilOut)
def perfil_de_perito(perito_id: UUID, db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    """El jefe de laboratorio y el fiscal ven la carga de cualquier perito."""
    if perito_id != usuario_actual.id and not puede(usuario_actual, "ver_perfil_ajeno"):
        raise HTTPException(status_code=403, detail="Solo puedes ver tu propio perfil.")
    perito = db.query(Usuario).filter(Usuario.id == perito_id, Usuario.rol.in_(ROLES_PERITO)).first()
    if not perito:
        raise HTTPException(status_code=404, detail="Perito no encontrado.")
    return _perfil(db, perito)
