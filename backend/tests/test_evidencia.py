"""Sprint 8 (historia 37): pruebas de hashes de evidencia y validación de subidas."""
import hashlib

import pytest
from fastapi import HTTPException

from app.services import hashing_service
from app.services.validacion_subida import validar_extension


def test_sha256_coincide_con_hashlib(tmp_path):
    archivo = tmp_path / "evidencia.txt"
    archivo.write_bytes(b"contenido de prueba")
    assert hashing_service.calcular_sha256(str(archivo)) == hashlib.sha256(b"contenido de prueba").hexdigest()


def test_un_byte_cambiado_rompe_la_integridad(tmp_path):
    archivo = tmp_path / "evidencia.txt"
    archivo.write_bytes(b"contenido de prueba")
    original = hashing_service.calcular_sha256(str(archivo))
    archivo.write_bytes(b"contenido de prueba!")
    assert not hashing_service.verificar_integridad(str(archivo), original)


def test_doble_hash_sha1_y_md5(tmp_path):
    archivo = tmp_path / "evidencia.bin"
    archivo.write_bytes(b"abc")
    h = hashing_service.calcular_hashes(str(archivo))
    assert h["sha1"] == hashlib.sha1(b"abc").hexdigest()
    assert h["md5"] == hashlib.md5(b"abc").hexdigest()


@pytest.mark.parametrize("nombre", ["virus.exe", "script.bat", "sin_extension"])
def test_extensiones_peligrosas_se_rechazan(nombre):
    with pytest.raises(HTTPException):
        validar_extension(nombre)


def test_extension_permitida_pasa():
    validar_extension("firma.png")
