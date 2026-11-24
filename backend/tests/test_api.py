"""Sprint 8 (historia 37): pruebas de la API contra una base de datos real (migrada con Alembic)."""
from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)


def test_cabeceras_de_seguridad_http():
    r = cliente.get("/docs")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert "x-frame-options" in {k.lower() for k in r.headers}


def test_sin_token_no_se_ven_casos():
    assert cliente.get("/casos").status_code == 401


def test_login_con_clave_incorrecta_falla():
    r = cliente.post("/auth/login", json={"email": "nadie@example.com", "password": "NoExiste2026"})
    assert r.status_code in (400, 401)


def test_qr_de_folio_inventado_dice_no_registrado():
    r = cliente.get("/v/r/FOLIO-INVENTADO-123")
    assert r.status_code == 404
    assert "Documento no registrado" in r.text
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-robots-tag"] == "noindex"


def test_blockchain_pide_sesion():
    # Sprint 8 (historia 39)
    assert cliente.get("/blockchain/anclajes").status_code == 401
    assert cliente.post("/blockchain/anclajes").status_code == 401
