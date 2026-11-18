"""Sprint 7 (historia 32): verificación pública por QR.

Cada reporte de auditoría y cada acta de juramento lleva un código QR. Al escanearlo con
el celular se abre una página SIN login que dice si el documento fue emitido por
CustodiaDigital y si su sello sigue siendo válido.

La página muestra solo lo mínimo: tipo de documento, folio, fecha, estado de los sellos y la
huella SHA-256 para comparar. Nunca datos del caso, de la evidencia ni de personas.

PUBLICO_BASE_URL es la dirección con la que el celular llega al servidor: en la demo,
http://<IP-de-la-PC-en-la-red>:8000 (con "localhost" el celular no la encuentra).
"""
import html
from datetime import timezone
from zoneinfo import ZoneInfo

from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.units import mm

from app.core.config import settings

LIMA = ZoneInfo("America/Lima")


# ---------------------------------------------------------------- direcciones

def _base() -> str:
    return settings.PUBLICO_BASE_URL.rstrip("/")


def url_reporte(folio: str) -> str:
    return f"{_base()}/v/r/{folio}"


def url_acta(designacion_id) -> str:
    return f"{_base()}/v/a/{designacion_id}"


# ---------------------------------------------------------------- QR para el PDF

def dibujo_qr(url: str, lado=26 * mm) -> Drawing:
    """Código QR listo para insertar en un PDF de ReportLab (sin librerías extra)."""
    qr = QrCodeWidget(url)
    qr.barBorder = 0
    x1, y1, x2, y2 = qr.getBounds()
    ancho, alto = x2 - x1, y2 - y1
    dibujo = Drawing(lado, lado, transform=[lado / ancho, 0, 0, lado / alto, 0, 0])
    dibujo.add(qr)
    return dibujo


# ---------------------------------------------------------------- página pública

def fecha_lima(dt) -> str:
    return dt.astimezone(LIMA).strftime("%d/%m/%Y %H:%M (hora de Lima)") if dt else "—"


def fecha_utc(dt) -> str:
    return dt.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M:%S UTC") if dt else "—"


def pagina(estado: str, titulo: str, mensaje: str, filas=None) -> str:
    """estado: valido | invalido | desconocido. filas: lista de (etiqueta, valor, es_codigo)."""
    colores = {
        "valido": ("#0f7a3d", "#e6f4ec", "✔"),
        "invalido": ("#b3261e", "#fbeaea", "✖"),
        "desconocido": ("#6b5a00", "#fbf5dc", "?"),
    }
    color, fondo, icono = colores.get(estado, colores["desconocido"])
    detalle = "".join(
        f"<tr><th>{html.escape(et)}</th>"
        f"<td class=\"{'cod' if cod else ''}\">{html.escape(str(val))}</td></tr>"
        for et, val, cod in (filas or [])
    )
    tabla = f"<table>{detalle}</table>" if detalle else ""
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Verificación · CustodiaDigital</title>
<style>
  body {{ margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         background: #f4f6f7; color: #1c2529; }}
  main {{ max-width: 560px; margin: 0 auto; padding: 24px 16px 40px; }}
  .marca {{ font-weight: 700; letter-spacing: .02em; color: #0e2a33; }}
  .marca small {{ display: block; font-weight: 500; font-size: 11px; letter-spacing: .12em;
                  color: #55666e; text-transform: uppercase; margin-top: 2px; }}
  .estado {{ margin: 20px 0; padding: 18px; border-radius: 12px; background: {fondo};
             border: 1px solid {color}; color: {color}; }}
  .estado h1 {{ margin: 0 0 6px; font-size: 22px; display: flex; gap: 10px; align-items: center; }}
  .estado p {{ margin: 0; color: #1c2529; line-height: 1.45; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 12px;
           overflow: hidden; border: 1px solid #d9e0e3; }}
  th, td {{ text-align: left; vertical-align: top; padding: 10px 12px; border-top: 1px solid #e8edef;
            font-size: 14px; }}
  tr:first-child th, tr:first-child td {{ border-top: 0; }}
  th {{ width: 38%; color: #55666e; font-weight: 600; }}
  td.cod {{ font-family: ui-monospace, Consolas, monospace; font-size: 12px; word-break: break-all; }}
  .nota {{ font-size: 12px; color: #55666e; line-height: 1.5; margin-top: 18px; }}
</style>
</head>
<body>
<main>
  <div class="marca">CustodiaDigital<small>Verificación pública de documentos</small></div>
  <section class="estado">
    <h1><span aria-hidden="true">{icono}</span>{html.escape(titulo)}</h1>
    <p>{html.escape(mensaje)}</p>
  </section>
  {tabla}
  <p class="nota">Esta página solo confirma la autenticidad del documento; no muestra datos del caso
  ni de la evidencia. Para comprobar que tu archivo es exactamente el emitido, compara su huella
  SHA-256 con la de esta página.</p>
</main>
</body>
</html>"""
