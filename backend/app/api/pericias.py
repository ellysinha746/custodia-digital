import json
import os
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.core.permisos import exigir, puede_ver_caso
from app.models.caso import Caso, EstadoCasoEnum
from app.models.pericia import Pericia, DesignacionPericia, ObservacionPericia
from app.models.usuario import Usuario, RolEnum
from app.services import pericia_service as reglas

# Sprint 5 (épica H19, historias 19.3 a 19.8): trámite de la pericia.
router = APIRouter(tags=["procedimiento pericial"])

MOTIVOS_SUBROGACION = {
    "negligencia": "Negligencia en el desempeño (CPP art. 175)",
    "impedimento": "Impedimento sobreviniente",
    "renuncia": "Renuncia del perito",
    "reasignacion": "Reasignación institucional",
    "otro": "Otro motivo",
}


# ----------------------------------------------------------------- esquemas
class PersonaOut(BaseModel):
    id: UUID
    nombre: str
    institucion: Optional[str] = None
    registro_profesional: Optional[str] = None


class DesignacionOut(BaseModel):
    id: UUID
    tipo: str
    perito: PersonaOut
    documento: Optional[str] = None
    designado_en: datetime
    activa: bool
    subrogado_en: Optional[datetime] = None
    motivo_subrogacion: Optional[str] = None
    documento_subrogacion: Optional[str] = None


class ObservacionOut(BaseModel):
    id: UUID
    autor: PersonaOut
    texto: str
    anexo_nombre: Optional[str] = None
    anexo_hash: Optional[str] = None
    creada_en: datetime
    respuesta: Optional[str] = None
    respondida_por: Optional[str] = None
    respondida_en: Optional[datetime] = None


class EventoOut(BaseModel):
    tipo: str
    detalle: Optional[str] = None
    usuario: str
    fecha: datetime


class ObjetivoOut(BaseModel):
    texto: str
    conclusion: Optional[str] = None


class PericiaOut(BaseModel):
    id: UUID
    codigo: str
    caso_id: UUID
    caso_numero: str
    estado: str
    estado_etiqueta: str
    disposicion_fiscal: str
    objetivos: List[ObjetivoOut]
    plazo_dias: int
    fecha_limite: datetime
    designada_por: str
    designada_en: datetime
    informe_nombre: Optional[str] = None
    informe_hash: Optional[str] = None
    emitida_en: Optional[datetime] = None
    traslado_en: Optional[datetime] = None
    traslado_vence_en: Optional[datetime] = None
    traslado_vencido: bool
    conocimiento_en: Optional[datetime] = None
    absuelta_en: Optional[datetime] = None
    concluida_en: Optional[datetime] = None
    perito_oficial: Optional[PersonaOut] = None
    peritos_parte: List[PersonaOut]
    designaciones: List[DesignacionOut]
    observaciones: List[ObservacionOut]
    eventos: List[EventoOut]
    acciones: List[str]


class DesignarIn(BaseModel):
    perito_oficial_id: UUID
    disposicion_fiscal: str = Field(min_length=1)
    objetivos: List[str] = Field(min_length=1)
    plazo_dias: int = Field(ge=1, le=365)


class TrasladoIn(BaseModel):
    plazo_dias: int = Field(ge=1, le=60)


class PeritoParteIn(BaseModel):
    perito_id: UUID
    documento: Optional[str] = None


class AbsolverIn(BaseModel):
    respuesta: str = Field(min_length=1)


class SubrogarIn(BaseModel):
    tipo: Literal["oficial", "parte"]
    saliente_id: UUID
    entrante_id: UUID
    motivo: Literal["negligencia", "impedimento", "renuncia", "reasignacion", "otro"]
    documento: str = Field(min_length=1)
    detalle: Optional[str] = None


# ----------------------------------------------------------------- utilidades
def _persona(u: Usuario) -> PersonaOut:
    return PersonaOut(id=u.id, nombre=u.nombre, institucion=u.institucion, registro_profesional=u.registro_profesional)


def _a_salida(p: Pericia, usuario) -> PericiaOut:
    oficiales = reglas.designacion_activa(p, "oficial")
    return PericiaOut(
        id=p.id,
        codigo=p.codigo,
        caso_id=p.caso_id,
        caso_numero=p.caso.numero_caso,
        estado=p.estado,
        estado_etiqueta=reglas.etiqueta_estado(p.estado),
        disposicion_fiscal=p.disposicion_fiscal,
        objetivos=[ObjetivoOut(**o) for o in p.objetivos],
        plazo_dias=p.plazo_dias,
        fecha_limite=p.fecha_limite,
        designada_por=p.designada_por.nombre,
        designada_en=p.designada_en,
        informe_nombre=p.informe_nombre,
        informe_hash=p.informe_hash,
        emitida_en=p.emitida_en,
        traslado_en=p.traslado_en,
        traslado_vence_en=p.traslado_vence_en,
        traslado_vencido=reglas.traslado_vencido(p),
        conocimiento_en=p.conocimiento_en,
        absuelta_en=p.absuelta_en,
        concluida_en=p.concluida_en,
        perito_oficial=_persona(oficiales[0].usuario) if oficiales else None,
        peritos_parte=[_persona(d.usuario) for d in reglas.designacion_activa(p, "parte")],
        designaciones=[
            DesignacionOut(
                id=d.id,
                tipo=d.tipo,
                perito=_persona(d.usuario),
                documento=d.documento,
                designado_en=d.designado_en,
                activa=d.activa,
                subrogado_en=d.subrogado_en,
                motivo_subrogacion=MOTIVOS_SUBROGACION.get(d.motivo_subrogacion, d.motivo_subrogacion),
                documento_subrogacion=d.documento_subrogacion,
            )
            for d in p.designaciones
        ],
        observaciones=[
            ObservacionOut(
                id=o.id,
                autor=_persona(o.autor),
                texto=o.texto,
                anexo_nombre=o.anexo_nombre,
                anexo_hash=o.anexo_hash,
                creada_en=o.creada_en,
                respuesta=o.respuesta,
                respondida_por=o.respondida_por.nombre if o.respondida_por else None,
                respondida_en=o.respondida_en,
            )
            for o in p.observaciones
        ],
        eventos=[EventoOut(tipo=e.tipo, detalle=e.detalle, usuario=e.usuario.nombre, fecha=e.fecha) for e in p.eventos],
        acciones=reglas.acciones_disponibles(p, usuario),
    )


def _obtener_caso(db: Session, caso_id: UUID, usuario) -> Caso:
    caso = db.query(Caso).filter(Caso.id == caso_id, Caso.eliminado_en.is_(None)).first()
    if not caso or not puede_ver_caso(db, usuario, caso):
        raise HTTPException(status_code=404, detail="Caso no encontrado.")
    return caso


def _obtener_pericia(db: Session, pericia_id: UUID, usuario) -> Pericia:
    pericia = db.query(Pericia).filter(Pericia.id == pericia_id).first()
    if not pericia:
        raise HTTPException(status_code=404, detail="Pericia no encontrada.")
    _obtener_caso(db, pericia.caso_id, usuario)
    return pericia


def _exigir_accion(pericia: Pericia, usuario, accion: str, mensaje: str) -> None:
    if accion not in reglas.acciones_disponibles(pericia, usuario):
        raise HTTPException(status_code=409, detail=mensaje)


def _perito_habilitado(db: Session, perito_id: UUID, rol: RolEnum) -> Usuario:
    perito = db.query(Usuario).filter(Usuario.id == perito_id).first()
    if not perito or perito.rol != rol:
        tipo = "perito oficial" if rol == RolEnum.perito else "perito de parte"
        raise HTTPException(status_code=400, detail=f"El usuario elegido no está registrado como {tipo}.")
    if not perito.activo:
        raise HTTPException(status_code=400, detail=f"{perito.nombre} está inhabilitado en el padrón.")
    return perito


def _fecha(dt: Optional[datetime]) -> str:
    return dt.astimezone(timezone(timedelta(hours=-5))).strftime("%d/%m/%Y %H:%M") if dt else "—"


# ----------------------------------------------------------------- lectura
@router.get("/casos/{caso_id}/pericias", response_model=List[PericiaOut])
def listar_pericias(caso_id: UUID, db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    _obtener_caso(db, caso_id, usuario_actual)
    pericias = db.query(Pericia).filter(Pericia.caso_id == caso_id).order_by(Pericia.designada_en.desc()).all()
    # Historia 19.7: lo que consulta el perito de parte queda registrado (cautela del procedimiento).
    if usuario_actual.rol == RolEnum.perito_parte:
        hace_poco = reglas.ahora() - timedelta(minutes=10)
        for p in pericias:
            if reglas.es_perito_parte(p, usuario_actual) and not any(
                e.tipo == "consulta" and e.usuario_id == usuario_actual.id and e.fecha and e.fecha > hace_poco
                for e in p.eventos
            ):
                reglas.registrar_evento(db, p, usuario_actual, "consulta", "El perito de parte revisó la pericia y el procedimiento.")
        db.commit()
        for p in pericias:
            db.refresh(p)
    return [_a_salida(p, usuario_actual) for p in pericias]


@router.get("/pericias/{pericia_id}", response_model=PericiaOut)
def obtener_pericia(pericia_id: UUID, db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    return _a_salida(_obtener_pericia(db, pericia_id, usuario_actual), usuario_actual)


@router.get("/pericias/{pericia_id}/informe")
def descargar_informe(pericia_id: UUID, db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    pericia = _obtener_pericia(db, pericia_id, usuario_actual)
    if not pericia.informe_ruta or not os.path.exists(pericia.informe_ruta):
        raise HTTPException(status_code=404, detail="La pericia aún no tiene informe emitido.")
    reglas.registrar_evento(db, pericia, usuario_actual, "descarga_informe", pericia.informe_nombre)
    db.commit()
    return FileResponse(pericia.informe_ruta, filename=f"{pericia.codigo}_{pericia.informe_nombre}")


@router.get("/observaciones-pericia/{observacion_id}/anexo")
def descargar_anexo(observacion_id: UUID, db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    obs = db.query(ObservacionPericia).filter(ObservacionPericia.id == observacion_id).first()
    if not obs or not obs.anexo_ruta:
        raise HTTPException(status_code=404, detail="Anexo no encontrado.")
    _obtener_pericia(db, obs.pericia_id, usuario_actual)
    if not os.path.exists(obs.anexo_ruta):
        raise HTTPException(status_code=404, detail="El anexo ya no está en el almacenamiento.")
    return FileResponse(obs.anexo_ruta, filename=obs.anexo_nombre)


@router.get("/pericias-motivos-subrogacion")
def motivos_subrogacion(usuario_actual=Depends(get_current_user)):
    return [{"valor": k, "etiqueta": v} for k, v in MOTIVOS_SUBROGACION.items()]


# ----------------------------------------------------------------- 19.3 designación
@router.post("/casos/{caso_id}/pericias", response_model=PericiaOut, status_code=status.HTTP_201_CREATED)
def designar_pericia(
    caso_id: UUID,
    payload: DesignarIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Historia 19.3: el fiscal designa al perito oficial con los objetivos de la pericia."""
    exigir(usuario_actual, "gestionar_pericias")
    caso = _obtener_caso(db, caso_id, usuario_actual)
    if caso.estado == EstadoCasoEnum.cerrado:
        raise HTTPException(status_code=409, detail="El caso está cerrado: no se pueden designar pericias.")
    perito = _perito_habilitado(db, payload.perito_oficial_id, RolEnum.perito)
    objetivos = [o.strip() for o in payload.objetivos if o.strip()]
    if not objetivos:
        raise HTTPException(status_code=400, detail="Indica al menos un objetivo de la pericia.")

    pericia = Pericia(
        caso_id=caso.id,
        codigo=reglas.nuevo_codigo(db),
        estado="designada",
        disposicion_fiscal=payload.disposicion_fiscal.strip(),
        objetivos=[{"texto": o, "conclusion": None} for o in objetivos],
        plazo_dias=payload.plazo_dias,
        fecha_limite=reglas.ahora() + timedelta(days=payload.plazo_dias),
        designada_por_id=usuario_actual.id,
    )
    db.add(pericia)
    db.flush()
    db.add(
        DesignacionPericia(
            pericia_id=pericia.id,
            usuario_id=perito.id,
            tipo="oficial",
            documento=pericia.disposicion_fiscal,
            designado_por_id=usuario_actual.id,
        )
    )
    reglas.registrar_evento(
        db, pericia, usuario_actual, "designacion",
        f"Designa a {perito.nombre} como perito oficial ({pericia.disposicion_fiscal}); {len(objetivos)} objetivo(s), plazo {payload.plazo_dias} día(s).",
    )
    db.commit()
    db.refresh(pericia)
    background_tasks.add_task(
        reglas.avisar, [perito.id], f"Designación pericial {pericia.codigo}",
        f"Fuiste designado perito oficial en el caso {caso.numero_caso} ({pericia.disposicion_fiscal}).\n"
        f"Plazo: {payload.plazo_dias} día(s), vence el {_fecha(pericia.fecha_limite)}.\n\nObjetivos:\n"
        + "\n".join(f"  {i + 1}. {o}" for i, o in enumerate(objetivos)),
    )
    return _a_salida(pericia, usuario_actual)


# ----------------------------------------------------------------- 19.4 emisión
@router.post("/pericias/{pericia_id}/emitir", response_model=PericiaOut)
def emitir_pericia(
    pericia_id: UUID,
    background_tasks: BackgroundTasks,
    informe: UploadFile = File(...),
    conclusiones: str = Form(...),
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Historia 19.4: el perito oficial sube su informe y una conclusión por objetivo.
    `conclusiones` es una lista JSON de textos, en el mismo orden que los objetivos."""
    pericia = _obtener_pericia(db, pericia_id, usuario_actual)
    _exigir_accion(pericia, usuario_actual, "emitir", "Solo el perito oficial designado puede emitir la pericia, y solo una vez.")
    try:
        lista = json.loads(conclusiones)
        assert isinstance(lista, list)
    except Exception:
        raise HTTPException(status_code=400, detail="Las conclusiones no tienen el formato correcto.")
    if len(lista) != len(pericia.objetivos) or any(not str(c).strip() for c in lista):
        raise HTTPException(status_code=400, detail="Escribe una conclusión para cada objetivo de la pericia.")

    nombre, ruta, h = reglas.guardar_documento(pericia, "informe", informe)
    pericia.informe_nombre, pericia.informe_ruta, pericia.informe_hash = nombre, ruta, h
    pericia.objetivos = [{"texto": o["texto"], "conclusion": str(c).strip()} for o, c in zip(pericia.objetivos, lista)]
    pericia.emitida_en = reglas.ahora()
    pericia.estado = "emitida"
    reglas.registrar_evento(db, pericia, usuario_actual, "emision", f"Informe {nombre} (SHA-256 {h[:16]}…)")
    db.commit()
    db.refresh(pericia)
    background_tasks.add_task(
        reglas.avisar, [pericia.designada_por_id], f"Pericia {pericia.codigo} emitida",
        f"{usuario_actual.nombre} emitió la pericia del caso {pericia.caso.numero_caso}. Ya puedes correr traslado.",
    )
    return _a_salida(pericia, usuario_actual)


# ----------------------------------------------------------------- 19.5 traslado y observaciones
@router.post("/pericias/{pericia_id}/traslado", response_model=PericiaOut)
def correr_traslado(
    pericia_id: UUID,
    payload: TrasladoIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    pericia = _obtener_pericia(db, pericia_id, usuario_actual)
    _exigir_accion(pericia, usuario_actual, "correr_traslado", "Solo el fiscal puede correr traslado, y solo de una pericia emitida.")
    pericia.traslado_en = reglas.ahora()
    pericia.traslado_plazo_dias = payload.plazo_dias
    pericia.traslado_vence_en = pericia.traslado_en + timedelta(days=payload.plazo_dias)
    pericia.estado = "en_traslado"
    reglas.registrar_evento(db, pericia, usuario_actual, "traslado", f"Corre traslado a la parte investigada por {payload.plazo_dias} día(s).")
    db.commit()
    db.refresh(pericia)
    partes = [d.usuario_id for d in reglas.designacion_activa(pericia, "parte")]
    if partes:
        background_tasks.add_task(
            reglas.avisar, partes, f"Traslado de la pericia {pericia.codigo}",
            f"Se corrió traslado de la pericia del caso {pericia.caso.numero_caso}.\n"
            f"Puedes formular observaciones hasta el {_fecha(pericia.traslado_vence_en)}.",
        )
    return _a_salida(pericia, usuario_actual)


@router.post("/pericias/{pericia_id}/observaciones", response_model=PericiaOut, status_code=status.HTTP_201_CREATED)
def observar_pericia(
    pericia_id: UUID,
    background_tasks: BackgroundTasks,
    texto: str = Form(...),
    anexo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Historia 19.5: el perito de parte registra las observaciones de la parte investigada."""
    pericia = _obtener_pericia(db, pericia_id, usuario_actual)
    if reglas.es_perito_parte(pericia, usuario_actual) and reglas.traslado_vencido(pericia):
        raise HTTPException(status_code=409, detail="El plazo del traslado ya venció: la observación sería extemporánea.")
    _exigir_accion(pericia, usuario_actual, "observar", "Solo el perito de parte designado puede observar, y solo durante el traslado.")
    if not texto.strip():
        raise HTTPException(status_code=400, detail="Escribe la observación.")

    obs = ObservacionPericia(pericia_id=pericia.id, autor_id=usuario_actual.id, texto=texto.strip())
    if anexo is not None and anexo.filename:
        obs.anexo_nombre, obs.anexo_ruta, obs.anexo_hash = reglas.guardar_documento(pericia, "observaciones", anexo)
    db.add(obs)
    pericia.estado = "observada"
    reglas.registrar_evento(db, pericia, usuario_actual, "observacion", texto.strip()[:140])
    db.commit()
    db.refresh(pericia)
    background_tasks.add_task(
        reglas.avisar, [pericia.designada_por_id], f"Pericia {pericia.codigo} observada",
        f"{usuario_actual.nombre} (perito de parte) observó la pericia del caso {pericia.caso.numero_caso}.",
    )
    return _a_salida(pericia, usuario_actual)


# ----------------------------------------------------------------- 19.6 conocimiento y absolución
@router.post("/pericias/{pericia_id}/conocimiento", response_model=PericiaOut)
def poner_en_conocimiento(
    pericia_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    pericia = _obtener_pericia(db, pericia_id, usuario_actual)
    _exigir_accion(pericia, usuario_actual, "poner_conocimiento", "Solo el fiscal puede poner en conocimiento, y solo una pericia observada.")
    pericia.conocimiento_en = reglas.ahora()
    pericia.estado = "en_absolucion"
    pendientes = sum(1 for o in pericia.observaciones if not o.respuesta)
    reglas.registrar_evento(db, pericia, usuario_actual, "conocimiento", f"Pone en conocimiento del perito oficial {pendientes} observación(es).")
    db.commit()
    db.refresh(pericia)
    oficiales = [d.usuario_id for d in reglas.designacion_activa(pericia, "oficial")]
    background_tasks.add_task(
        reglas.avisar, oficiales, f"Observaciones a la pericia {pericia.codigo}",
        f"El fiscal te pone en conocimiento {pendientes} observación(es) a tu pericia del caso {pericia.caso.numero_caso}. Debes absolverlas.",
    )
    return _a_salida(pericia, usuario_actual)


@router.post("/observaciones-pericia/{observacion_id}/absolver", response_model=PericiaOut)
def absolver_observacion(
    observacion_id: UUID,
    payload: AbsolverIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    obs = db.query(ObservacionPericia).filter(ObservacionPericia.id == observacion_id).first()
    if not obs:
        raise HTTPException(status_code=404, detail="Observación no encontrada.")
    pericia = _obtener_pericia(db, obs.pericia_id, usuario_actual)
    _exigir_accion(pericia, usuario_actual, "absolver", "Solo el perito oficial puede absolver, después de que el fiscal lo ponga en conocimiento.")
    if obs.respuesta:
        raise HTTPException(status_code=409, detail="Esta observación ya fue absuelta.")
    obs.respuesta = payload.respuesta.strip()
    obs.respondida_por_id = usuario_actual.id
    obs.respondida_en = reglas.ahora()
    reglas.registrar_evento(db, pericia, usuario_actual, "absolucion", payload.respuesta.strip()[:140])
    db.flush()
    db.refresh(pericia)
    if all(o.respuesta for o in pericia.observaciones):
        pericia.estado = "absuelta"
        pericia.absuelta_en = reglas.ahora()
        reglas.registrar_evento(db, pericia, usuario_actual, "absuelta", "Todas las observaciones fueron absueltas.")
        background_tasks.add_task(
            reglas.avisar, [pericia.designada_por_id] + [d.usuario_id for d in reglas.designacion_activa(pericia, "parte")],
            f"Pericia {pericia.codigo} absuelta",
            f"El perito oficial absolvió todas las observaciones de la pericia del caso {pericia.caso.numero_caso}.",
        )
    db.commit()
    db.refresh(pericia)
    return _a_salida(pericia, usuario_actual)


@router.post("/pericias/{pericia_id}/concluir", response_model=PericiaOut)
def concluir_pericia(pericia_id: UUID, db: Session = Depends(get_db), usuario_actual=Depends(get_current_user)):
    pericia = _obtener_pericia(db, pericia_id, usuario_actual)
    _exigir_accion(pericia, usuario_actual, "concluir", "Solo el fiscal puede concluir, cuando no hay observaciones pendientes.")
    detalle = "Sin observaciones de la parte." if pericia.estado == "en_traslado" else "Observaciones absueltas."
    pericia.estado = "concluida"
    pericia.concluida_en = reglas.ahora()
    reglas.registrar_evento(db, pericia, usuario_actual, "conclusion", detalle)
    db.commit()
    db.refresh(pericia)
    return _a_salida(pericia, usuario_actual)


# ----------------------------------------------------------------- 19.7 perito de parte
@router.post("/pericias/{pericia_id}/perito-parte", response_model=PericiaOut)
def designar_perito_parte(
    pericia_id: UUID,
    payload: PeritoParteIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Historia 19.7: el fiscal acredita al perito de parte designado por la parte investigada."""
    pericia = _obtener_pericia(db, pericia_id, usuario_actual)
    _exigir_accion(pericia, usuario_actual, "designar_parte", "Solo el fiscal puede acreditar al perito de parte, antes de concluir la pericia.")
    perito = _perito_habilitado(db, payload.perito_id, RolEnum.perito_parte)
    if reglas.es_perito_parte(pericia, perito):
        raise HTTPException(status_code=409, detail=f"{perito.nombre} ya está acreditado en esta pericia.")
    db.add(
        DesignacionPericia(
            pericia_id=pericia.id, usuario_id=perito.id, tipo="parte",
            documento=(payload.documento or "").strip() or None, designado_por_id=usuario_actual.id,
        )
    )
    reglas.registrar_evento(db, pericia, usuario_actual, "designacion_parte", f"Acredita a {perito.nombre} como perito de parte.")
    db.commit()
    db.refresh(pericia)
    background_tasks.add_task(
        reglas.avisar, [perito.id], f"Acreditación como perito de parte - {pericia.codigo}",
        f"Fuiste acreditado como perito de parte en el caso {pericia.caso.numero_caso}. Puedes revisar el procedimiento del perito oficial.",
    )
    return _a_salida(pericia, usuario_actual)


# ----------------------------------------------------------------- 19.8 subrogación
@router.post("/pericias/{pericia_id}/subrogar", response_model=PericiaOut)
def subrogar_perito(
    pericia_id: UUID,
    payload: SubrogarIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Historia 19.8 (CPP art. 175): reemplaza a un perito. El saliente pierde el acceso
    al instante, pero su designación NO se borra: queda en el historial como subrogado."""
    pericia = _obtener_pericia(db, pericia_id, usuario_actual)
    _exigir_accion(pericia, usuario_actual, "subrogar", "Solo el fiscal puede subrogar peritos, antes de concluir la pericia.")
    saliente = next(
        (d for d in reglas.designacion_activa(pericia, payload.tipo) if d.usuario_id == payload.saliente_id), None
    )
    if not saliente:
        raise HTTPException(status_code=400, detail="El perito saliente no está designado actualmente en esta pericia.")
    if payload.entrante_id == payload.saliente_id:
        raise HTTPException(status_code=400, detail="El perito entrante debe ser distinto del saliente.")
    rol = RolEnum.perito if payload.tipo == "oficial" else RolEnum.perito_parte
    entrante = _perito_habilitado(db, payload.entrante_id, rol)

    saliente.activa = False
    saliente.subrogado_en = reglas.ahora()
    saliente.motivo_subrogacion = payload.motivo
    saliente.documento_subrogacion = payload.documento.strip()
    saliente.subrogado_por_id = usuario_actual.id
    db.add(
        DesignacionPericia(
            pericia_id=pericia.id, usuario_id=entrante.id, tipo=payload.tipo,
            documento=payload.documento.strip(), designado_por_id=usuario_actual.id,
        )
    )
    nombre_saliente = saliente.usuario.nombre
    reglas.registrar_evento(
        db, pericia, usuario_actual, "subrogacion",
        f"Subroga a {nombre_saliente} por {entrante.nombre} ({MOTIVOS_SUBROGACION[payload.motivo]}; {payload.documento.strip()})"
        + (f". {payload.detalle.strip()}" if payload.detalle and payload.detalle.strip() else ""),
    )
    db.commit()
    db.refresh(pericia)
    background_tasks.add_task(
        reglas.avisar, [saliente.usuario_id, entrante.id], f"Subrogación de perito - {pericia.codigo}",
        f"En la pericia del caso {pericia.caso.numero_caso}, {nombre_saliente} fue subrogado por {entrante.nombre}.\n"
        f"Motivo: {MOTIVOS_SUBROGACION[payload.motivo]}. Documento: {payload.documento.strip()}.",
    )
    return _a_salida(pericia, usuario_actual)
