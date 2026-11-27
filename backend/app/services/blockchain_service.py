"""Sprint 8 (historia 39): anclaje del historial de custodia en Bitcoin con OpenTimestamps.

Cómo funciona:
1. Se arma el "historial canónico": todos los registros de la cadena de custodia hasta un momento,
   uno por línea y siempre en el mismo orden y formato.
2. Se calcula su SHA-256 (la "huella"). A Bitcoin solo viaja esa huella: ningún dato del caso,
   de la evidencia ni de las personas sale del laboratorio.
3. Los calendarios públicos de OpenTimestamps juntan muchas huellas y las anclan en un bloque de
   Bitcoin (tarda unas horas). Devuelven una prueba .ots que guardamos.
4. Para verificar se vuelve a armar el historial desde la base de datos: si alguien cambió,
   borró o insertó un registro anterior, la huella ya no coincide con la anclada.

Cualquiera puede comprobarlo por su cuenta en https://opentimestamps.org subiendo el historial
(.txt) y su prueba (.ots).
"""
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from opentimestamps.calendar import CommitmentNotFoundError, RemoteCalendar
from opentimestamps.core.notary import BitcoinBlockHeaderAttestation, PendingAttestation
from opentimestamps.core.op import OpSHA256
from opentimestamps.core.serialize import BytesDeserializationContext, BytesSerializationContext
from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.anclaje_blockchain import AnclajeBlockchain
from app.models.log_custodia import LogCustodia

# Calendarios públicos y gratuitos a los que se envía la huella (con uno que responda basta).
CALENDARIOS = [
    "https://a.pool.opentimestamps.org",
    "https://b.pool.opentimestamps.org",
    "https://a.pool.eternitywall.com",
]
# Solo se consulta a estos servidores al actualizar una prueba (la prueba podría traer otra dirección).
DOMINIOS_CONFIABLES = (".opentimestamps.org", ".eternitywall.com", ".catallaxy.com")


class SinCalendarios(Exception):
    """Ningún calendario de OpenTimestamps respondió (por ejemplo, sin internet)."""


# ---------------------------------------------------------------- historial y huella

def historial_canonico(db: Session, hasta: datetime) -> Tuple[bytes, int]:
    """Todos los registros de custodia con fecha <= hasta, en orden fijo. (texto, cantidad)."""
    filas = (
        db.query(LogCustodia)
        .filter(LogCustodia.fecha <= hasta)
        .order_by(LogCustodia.fecha, LogCustodia.id)
        .all()
    )
    lineas = [
        "CustodiaDigital - historial de la cadena de custodia",
        f"hasta: {hasta.astimezone(timezone.utc).isoformat()}",
        f"registros: {len(filas)}",
        "id|archivo|usuario|accion|fecha_utc|resultado",
    ]
    for f in filas:
        resultado = (f.resultado or "").replace("\n", " ").replace("|", "/")
        lineas.append(
            f"{f.id}|{f.archivo_id}|{f.usuario_id}|{f.accion.value}|"
            f"{f.fecha.astimezone(timezone.utc).isoformat()}|{resultado}"
        )
    return ("\n".join(lineas) + "\n").encode("utf-8"), len(filas)


def _a_bytes(prueba: DetachedTimestampFile) -> bytes:
    ctx = BytesSerializationContext()
    prueba.serialize(ctx)
    return ctx.getbytes()


def _de_bytes(datos: bytes) -> DetachedTimestampFile:
    return DetachedTimestampFile.deserialize(BytesDeserializationContext(datos))


def _bloques(timestamp: Timestamp) -> List[int]:
    return sorted(a.height for _, a in timestamp.all_attestations() if isinstance(a, BitcoinBlockHeaderAttestation))


def _nodos(timestamp: Timestamp):
    yield timestamp
    for sub in timestamp.ops.values():
        yield from _nodos(sub)


def _confiable(url: str) -> bool:
    p = urlparse(url)
    return p.scheme == "https" and any((p.hostname or "").endswith(d) for d in DOMINIOS_CONFIABLES)


# ---------------------------------------------------------------- operaciones

def anclar(db: Session, usuario_id=None) -> AnclajeBlockchain:
    """Calcula la huella del historial hasta ahora y la envía a los calendarios."""
    hasta = db.query(func.now()).scalar()  # la hora de la BASE: la misma con que se guardan los registros
    texto, total = historial_canonico(db, hasta)
    huella = hashlib.sha256(texto).digest()

    timestamp = Timestamp(huella)
    aceptaron = []
    for url in CALENDARIOS:
        try:
            timestamp.merge(RemoteCalendar(url).submit(huella, timeout=settings.BLOCKCHAIN_TIMEOUT_SEG))
            aceptaron.append(url)
        except Exception as e:  # un calendario caído no impide usar los otros
            print(f"[blockchain] {url} no respondió: {e}", flush=True)
    if not aceptaron:
        raise SinCalendarios("No se pudo contactar ningún calendario de OpenTimestamps. Revisa la conexión a internet.")

    bloques = _bloques(timestamp)
    anclaje = AnclajeBlockchain(
        creado_en=datetime.now(timezone.utc), creado_por_id=usuario_id, hasta=hasta, total_registros=total,
        huella=huella.hex(), prueba_ots=_a_bytes(DetachedTimestampFile(OpSHA256(), timestamp)),
        calendarios=aceptaron, estado="confirmado" if bloques else "pendiente",
        bloque_bitcoin=bloques[0] if bloques else None,
    )
    db.add(anclaje)
    db.commit()
    db.refresh(anclaje)
    return anclaje


def actualizar(db: Session, anclaje: AnclajeBlockchain) -> AnclajeBlockchain:
    """Pide a los calendarios la parte de la prueba que llega cuando Bitcoin confirma el bloque."""
    prueba = _de_bytes(anclaje.prueba_ots)
    for nodo in list(_nodos(prueba.timestamp)):
        for att in list(nodo.attestations):
            if not isinstance(att, PendingAttestation) or not _confiable(att.uri):
                continue
            try:
                nodo.merge(RemoteCalendar(att.uri).get_timestamp(nodo.msg, timeout=settings.BLOCKCHAIN_TIMEOUT_SEG))
            except CommitmentNotFoundError:
                pass  # el calendario todavía no lo incluye en un bloque
            except Exception as e:
                print(f"[blockchain] {att.uri} no respondió: {e}", flush=True)
    bloques = _bloques(prueba.timestamp)
    anclaje.prueba_ots = _a_bytes(prueba)
    anclaje.actualizado_en = datetime.now(timezone.utc)
    if bloques:
        anclaje.estado, anclaje.bloque_bitcoin = "confirmado", bloques[0]
    db.commit()
    db.refresh(anclaje)
    return anclaje


def verificar(db: Session, anclaje: AnclajeBlockchain) -> Dict:
    """Rearma el historial desde la base y lo compara con la huella anclada."""
    texto, total = historial_canonico(db, anclaje.hasta)
    huella_actual = hashlib.sha256(texto).hexdigest()
    prueba = _de_bytes(anclaje.prueba_ots)
    prueba_coincide = prueba.file_digest.hex() == anclaje.huella
    intacto = prueba_coincide and huella_actual == anclaje.huella
    if intacto:
        mensaje = "El historial de custodia hasta esa fecha está intacto: coincide con la huella anclada."
    elif not prueba_coincide:
        mensaje = "La prueba .ots guardada no corresponde a la huella registrada: el anclaje fue manipulado."
    elif total != anclaje.total_registros:
        mensaje = (
            f"El historial NO coincide con la huella anclada: se anclaron {anclaje.total_registros} registros "
            f"hasta esa fecha y hoy hay {total}. Se borraron o insertaron registros."
        )
    else:
        mensaje = "El historial NO coincide con la huella anclada: al menos un registro anterior fue modificado."
    return {
        "intacto": intacto,
        "mensaje": mensaje,
        "huella_anclada": anclaje.huella,
        "huella_actual": huella_actual,
        "registros_anclados": anclaje.total_registros,
        "registros_actuales": total,
        "estado": anclaje.estado,
        "bloque_bitcoin": anclaje.bloque_bitcoin,
    }


def ultimo(db: Session) -> Optional[AnclajeBlockchain]:
    return db.query(AnclajeBlockchain).order_by(AnclajeBlockchain.hasta.desc()).first()


def tarea_automatica(db: Session) -> str:
    """Para el proceso en segundo plano: actualiza los pendientes y ancla si hay registros nuevos
    y ya pasaron BLOCKCHAIN_CADA_HORAS desde el último anclaje."""
    for a in db.query(AnclajeBlockchain).filter(AnclajeBlockchain.estado == "pendiente").all():
        actualizar(db, a)
    previo = ultimo(db)
    if previo:
        horas = (datetime.now(timezone.utc) - previo.hasta).total_seconds() / 3600
        nuevos = db.query(func.count(LogCustodia.id)).filter(LogCustodia.fecha > previo.hasta).scalar()
        if horas < settings.BLOCKCHAIN_CADA_HORAS or not nuevos:
            return "sin cambios"
    elif not db.query(LogCustodia.id).first():
        return "sin registros"
    a = anclar(db)
    return f"anclados {a.total_registros} registros"
