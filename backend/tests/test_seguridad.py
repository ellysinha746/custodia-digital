"""Sprint 8 (historia 37): pruebas de las reglas de seguridad (HU27) y de los sellos HMAC."""
import pytest
from fastapi import HTTPException

from app.core import sello
from app.core.security import validar_password, hash_password, verify_password


@pytest.mark.parametrize("clave", ["corta1", "solamenteletras", "1234567890"])
def test_password_debil_se_rechaza(clave):
    with pytest.raises(HTTPException) as e:
        validar_password(clave)
    assert e.value.status_code == 400


def test_password_fuerte_se_acepta():
    validar_password("Demo2026!x")  # no lanza error


def test_hash_de_password_no_guarda_la_clave_en_claro():
    h = hash_password("Demo2026!x")
    assert "Demo2026" not in h
    assert verify_password("Demo2026!x", h)
    assert not verify_password("otraClave123", h)


def test_sello_detecta_documento_alterado():
    firma = sello.firmar(b"reporte folio 0001")
    assert sello.firma_valida(b"reporte folio 0001", firma)
    assert not sello.firma_valida(b"reporte folio 0002", firma)
    assert not sello.firma_valida(b"reporte folio 0001", "0" * 64)
