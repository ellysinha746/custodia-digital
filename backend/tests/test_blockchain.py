"""Sprint 8 (historia 39): anclaje del historial de custodia con OpenTimestamps.

Los calendarios de OpenTimestamps se SIMULAN (sin internet). Todo se hace dentro de una
transacción que se deshace al final: la prueba no deja datos en la base."""
import os
import uuid
from datetime import timedelta

import pytest
from opentimestamps.core.notary import BitcoinBlockHeaderAttestation, PendingAttestation
from opentimestamps.core.op import OpAppend, OpSHA256
from opentimestamps.core.timestamp import Timestamp
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.archivo import Archivo
from app.models.caso import Caso
from app.models.log_custodia import AccionEnum, LogCustodia
from app.models.usuario import Usuario
from app.services import blockchain_service


class CalendarioFalso:
    """Imita a un calendario: primero devuelve una prueba pendiente; luego, la confirmación."""
    confirmado = False

    def __init__(self, url):
        self.url = url

    def submit(self, digest, timeout=None):
        t = Timestamp(digest)
        hoja = t.ops.add(OpAppend(b"nonce-de-prueba")).ops.add(OpSHA256())
        hoja.attestations.add(PendingAttestation("https://alice.btc.calendar.opentimestamps.org"))
        return t

    def get_timestamp(self, commitment, timeout=None):
        if not CalendarioFalso.confirmado:
            raise blockchain_service.CommitmentNotFoundError("todavía no")
        t = Timestamp(commitment)
        t.attestations.add(BitcoinBlockHeaderAttestation(925000))
        return t


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setattr(blockchain_service, "RemoteCalendar", CalendarioFalso)
    CalendarioFalso.confirmado = False
    motor = create_engine(os.environ["DATABASE_URL"])
    conexion = motor.connect()
    transaccion = conexion.begin()
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint")
    yield sesion
    sesion.close()
    transaccion.rollback()  # nada de lo que hizo la prueba queda en la base
    conexion.close()


def _registro(db, n=3):
    sufijo = uuid.uuid4().hex[:8]
    u = Usuario(nombre="Perito de prueba", email=f"perito.{sufijo}@example.com", password_hash="x")
    db.add(u)
    db.flush()
    c = Caso(numero_caso=f"PRUEBA-{sufijo}", especialidad="informatica", usuario_id=u.id)
    db.add(c)
    db.flush()
    a = Archivo(caso_id=c.id, nombre_original="evidencia.bin", ruta_original="x", ruta_copia_trabajo="y")
    db.add(a)
    db.flush()
    logs = [LogCustodia(archivo_id=a.id, usuario_id=u.id, accion=AccionEnum.acceso, resultado=f"acceso {i}") for i in range(n)]
    db.add_all(logs)
    db.commit()
    return logs


def test_anclar_y_verificar_historial_intacto(db):
    _registro(db)
    anclaje = blockchain_service.anclar(db)
    assert anclaje.estado == "pendiente"
    assert len(anclaje.huella) == 64
    assert blockchain_service.verificar(db, anclaje)["intacto"]


def test_cambiar_un_registro_anterior_se_detecta(db):
    logs = _registro(db)
    anclaje = blockchain_service.anclar(db)
    logs[1].resultado = "descarga borrada a escondidas"  # alguien edita la base
    db.commit()
    r = blockchain_service.verificar(db, anclaje)
    assert not r["intacto"]
    assert r["huella_actual"] != r["huella_anclada"]


def test_borrar_un_registro_anterior_se_detecta(db):
    logs = _registro(db)
    anclaje = blockchain_service.anclar(db)
    db.delete(logs[0])
    db.commit()
    r = blockchain_service.verificar(db, anclaje)
    assert not r["intacto"] and r["registros_actuales"] == r["registros_anclados"] - 1


def test_registros_nuevos_no_afectan_un_anclaje_anterior(db):
    logs = _registro(db)
    anclaje = blockchain_service.anclar(db)
    db.add(LogCustodia(archivo_id=logs[0].archivo_id, usuario_id=logs[0].usuario_id,
                       accion=AccionEnum.verificacion, fecha=anclaje.hasta + timedelta(seconds=5)))
    db.commit()
    assert blockchain_service.verificar(db, anclaje)["intacto"]


def test_actualizar_cuando_bitcoin_confirma(db):
    _registro(db)
    anclaje = blockchain_service.anclar(db)
    assert blockchain_service.actualizar(db, anclaje).estado == "pendiente"  # aún sin bloque
    CalendarioFalso.confirmado = True
    anclaje = blockchain_service.actualizar(db, anclaje)
    assert anclaje.estado == "confirmado" and anclaje.bloque_bitcoin == 925000
    assert blockchain_service.verificar(db, anclaje)["intacto"]


def test_sin_internet_avisa(db, monkeypatch):
    class Caido(CalendarioFalso):
        def submit(self, digest, timeout=None):
            raise OSError("sin red")
    monkeypatch.setattr(blockchain_service, "RemoteCalendar", Caido)
    with pytest.raises(blockchain_service.SinCalendarios):
        blockchain_service.anclar(db)


def test_solo_se_consultan_calendarios_confiables():
    assert blockchain_service._confiable("https://alice.btc.calendar.opentimestamps.org")
    assert not blockchain_service._confiable("http://alice.btc.calendar.opentimestamps.org")
    assert not blockchain_service._confiable("https://opentimestamps.org.atacante.com")
