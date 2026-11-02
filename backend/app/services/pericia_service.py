import os
import shutil
import uuid
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.pericia import Pericia, DesignacionPericia, EventoPericia, ESTADOS_PERICIA
from app.models.usuario import Usuario, RolEnum
from app.services.correo_service import enviar_correo
from app.services.hashing_service import calcular_sha256
from app.services.storage_service import STORAGE_DIR

# Sprint 5 (épica H19): reglas del procedimiento pericial.


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def nuevo_codigo(db: Session) -> str:
    anio = ahora().year
    total = db.query(Pericia).filter(Pericia.codigo.like(f"PER-{anio}-%")).count()
    return f"PER-{anio}-{total + 1:04d}"


def designacion_activa(pericia: Pericia, tipo: str) -> List[DesignacionPericia]:
    return [d for d in pericia.designaciones if d.tipo == tipo and d.activa]


def es_perito_oficial(pericia: Pericia, usuario) -> bool:
    return any(d.usuario_id == usuario.id for d in designacion_activa(pericia, "oficial"))


def es_perito_parte(pericia: Pericia, usuario) -> bool:
    return any(d.usuario_id == usuario.id for d in designacion_activa(pericia, "parte"))


def dirige(usuario) -> bool:
    """El fiscal (o el jefe de laboratorio) dirige el trámite."""
    return usuario.rol in (RolEnum.fiscal, RolEnum.admin)


def traslado_vencido(pericia: Pericia) -> bool:
    return pericia.traslado_vence_en is not None and ahora() > pericia.traslado_vence_en


def acciones_disponibles(pericia: Pericia, usuario) -> List[str]:
    """Qué puede hacer ESTE usuario con la pericia en su estado actual.
    El frontend solo muestra estos botones; el backend vuelve a validar cada uno."""
    e = pericia.estado
    acciones = []
    if e == "concluida":
        return acciones
    if es_perito_oficial(pericia, usuario) and e == "designada":
        acciones.append("emitir")
    if dirige(usuario):
        acciones.append("subrogar")
        acciones.append("designar_parte")
        if e == "emitida":
            acciones.append("correr_traslado")
        if e == "observada":
            acciones.append("poner_conocimiento")
        if e in ("en_traslado", "absuelta"):
            acciones.append("concluir")
    if es_perito_parte(pericia, usuario) and e in ("en_traslado", "observada") and not traslado_vencido(pericia):
        acciones.append("observar")
    if es_perito_oficial(pericia, usuario) and e == "en_absolucion":
        acciones.append("absolver")
    return acciones


def registrar_evento(db: Session, pericia: Pericia, usuario, tipo: str, detalle: Optional[str] = None) -> None:
    db.add(EventoPericia(pericia_id=pericia.id, usuario_id=usuario.id, tipo=tipo, detalle=detalle))


def guardar_documento(pericia: Pericia, subcarpeta: str, archivo) -> tuple:
    """Guarda el informe pericial o un anexo aparte de la evidencia. Devuelve (nombre, ruta, sha256)."""
    carpeta = os.path.join(STORAGE_DIR, str(pericia.caso_id), "pericias", str(pericia.id), subcarpeta, uuid.uuid4().hex)
    os.makedirs(carpeta, exist_ok=True)
    nombre = os.path.basename(archivo.filename or "documento")
    ruta = os.path.join(carpeta, nombre)
    with open(ruta, "wb") as destino:
        shutil.copyfileobj(archivo.file, destino)
    return nombre, ruta, calcular_sha256(ruta)


def avisar(usuario_ids: Iterable, asunto: str, cuerpo: str) -> None:
    """Correo a los usuarios indicados (corre en segundo plano, abre su propia sesión)."""
    db = SessionLocal()
    try:
        correos = [u.email for u in db.query(Usuario).filter(Usuario.id.in_(list(usuario_ids))).all()]
    finally:
        db.close()
    enviar_correo(correos, f"[CustodiaDigital] {asunto}", cuerpo + "\n\nIngresa a CustodiaDigital para ver el detalle.")


def etiqueta_estado(estado: str) -> str:
    return ESTADOS_PERICIA.get(estado, estado)
