from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.pericia import DesignacionPericia
from app.models.reporte_auditoria import ReporteAuditoria
from app.services import tsa_service
from app.services.acta_juramento_service import acta_integra, mensaje_acta
from app.services.reporte_service import firma_valida, mensaje_sello
from app.services.verificacion_publica import fecha_lima, fecha_utc, pagina

# Sprint 7 (historia 32): páginas públicas (sin login) a las que llevan los QR de los PDF.
router = APIRouter(prefix="/v", tags=["verificación pública"])

CABECERAS = {
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex",
    # Página estática: no carga nada externo ni ejecuta scripts.
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'",
}


def _respuesta(contenido: str, codigo: int = 200) -> HTMLResponse:
    return HTMLResponse(contenido, status_code=codigo, headers=CABECERAS)


def _no_registrado() -> HTMLResponse:
    return _respuesta(
        pagina(
            "invalido",
            "Documento no registrado",
            "Este código no corresponde a ningún documento emitido por CustodiaDigital. "
            "No confíes en el documento.",
        ),
        404,
    )


def _fila_tsa(token, datos: bytes, fecha):
    """Estado del sello RFC 3161 (Sprint 6, historia 21). Devuelve (fila, válido o None)."""
    if not token:
        return ("Sello de tiempo RFC 3161", "No tiene (la autoridad de sellado no respondió)", False), None
    valido = tsa_service.verificar(datos, token)
    texto = f"Válido · {fecha_utc(fecha)} · {settings.TSA_NOMBRE}" if valido else "NO corresponde al documento"
    return ("Sello de tiempo RFC 3161", texto, False), valido


@router.get("/r/{folio}", response_class=HTMLResponse)
def verificar_reporte_publico(folio: str, db: Session = Depends(get_db)):
    r = db.query(ReporteAuditoria).filter(ReporteAuditoria.folio == folio).first()
    if not r:
        return _no_registrado()

    sello_ok = firma_valida(r.folio, r.generado_en, r.hash_contenido, r.firma)
    fila_tsa, tsa_ok = _fila_tsa(r.tsa_token, mensaje_sello(r.folio, r.generado_en, r.hash_contenido), r.tsa_fecha)
    autentico = sello_ok and tsa_ok is not False

    filas = [
        ("Documento", "Reporte de auditoría de la cadena de custodia", False),
        ("Folio", r.folio, True),
        ("Emitido", fecha_lima(r.generado_en), False),
        ("Sello del servidor", "Válido" if sello_ok else "NO válido", False),
        fila_tsa,
        ("Huella SHA-256 del archivo oficial", r.hash_archivo, True),
    ]
    if autentico:
        return _respuesta(pagina(
            "valido", "Documento auténtico",
            "Este reporte fue emitido por CustodiaDigital y sus sellos siguen siendo válidos.", filas))
    return _respuesta(pagina(
        "invalido", "Sello no válido",
        "El reporte está registrado, pero su sello no coincide: el registro pudo haber sido alterado.", filas))


@router.get("/a/{designacion_id}", response_class=HTMLResponse)
def verificar_acta_publica(designacion_id: str, db: Session = Depends(get_db)):
    try:
        uid = UUID(designacion_id)
    except ValueError:
        return _no_registrado()
    d = db.query(DesignacionPericia).filter(DesignacionPericia.id == uid).first()
    if not d or not d.juramento_en:
        return _no_registrado()

    integra = acta_integra(d)
    fila_tsa, tsa_ok = _fila_tsa(
        d.juramento_tsa_token, mensaje_acta(d.id, d.juramento_hash or ""), d.juramento_tsa_fecha
    )
    autentica = integra and tsa_ok is not False

    filas = [
        ("Documento", "Acta de aceptación del cargo y juramento de perito (CPP art. 174)", False),
        ("Fecha del juramento", fecha_lima(d.juramento_en), False),
        ("Integridad del registro", "Verificada" if integra else "NO coincide", False),
        fila_tsa,
        ("Huella SHA-256 del acta", d.juramento_hash or "—", True),
    ]
    if autentica:
        return _respuesta(pagina(
            "valido", "Acta auténtica",
            "Esta acta fue registrada en CustodiaDigital y no fue modificada desde el juramento.", filas))
    return _respuesta(pagina(
        "invalido", "Acta alterada",
        "El acta está registrada, pero su contenido ya no coincide con lo jurado.", filas))
