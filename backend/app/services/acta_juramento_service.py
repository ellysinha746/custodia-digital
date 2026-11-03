import hashlib
import hmac
import io
import json
import unicodedata
from datetime import datetime, timedelta, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from app.core.config import settings

# Sprint 5: acta de aceptación del cargo y juramento del perito oficial (CPP art. 174).
# El texto jurado se guarda tal cual; su SHA-256 y una firma HMAC del servidor
# permiten comprobar después que el acta no fue alterada.

FORMAS = {
    "juramento": "JURO",
    "promesa": "PROMETO POR MI HONOR",
}

MOTIVOS_INHIBICION = {
    "parentesco": "Parentesco con alguna de las partes",
    "amistad_enemistad": "Amistad íntima o enemistad con alguna de las partes",
    "interes": "Interés en el resultado del proceso",
    "testigo": "Fue testigo del hecho investigado",
    "perito_parte": "Actuó como perito de parte en este proceso",
    "grave_impedimento": "Grave impedimento (salud, carga laboral u otro)",
    "otro": "Otro motivo",
}

ETIQUETA_ESPECIALIDAD = {"audio": "audio", "video": "video", "informatica": "informática", "telefonia": "telefonía"}

PERU = timezone(timedelta(hours=-5))


def normalizar_nombre(texto: str) -> str:
    """Para comparar la firma escrita con el nombre registrado (sin tildes, mayúsculas ni espacios de más)."""
    sin_tildes = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.casefold().split())


def texto_juramento(forma: str, perito, pericia, documento: str = None) -> str:
    datos = ", ".join(x for x in [perito.institucion, perito.registro_profesional] if x)
    especialidad = ETIQUETA_ESPECIALIDAD.get(pericia.especialidad or "", pericia.especialidad or "")
    return (
        f"Yo, {perito.nombre}{f' ({datos})' if datos else ''}, {FORMAS[forma]} desempeñar con verdad y diligencia "
        f"el cargo de perito oficial{f' de {especialidad}' if especialidad else ''} en la pericia {pericia.codigo} "
        f"del caso {pericia.caso.numero_caso}, para el que fui designado mediante {documento or pericia.disposicion_fiscal}. "
        "Declaro que no me encuentro incurso en ninguna causal de impedimento para ejercer el cargo "
        "y que guardaré reserva sobre la información y la evidencia a la que acceda."
    )


def hash_acta(designacion, texto: str, fecha: datetime, forma: str) -> str:
    contenido = {
        "designacion": str(designacion.id),
        "pericia": designacion.pericia.codigo,
        "caso": designacion.pericia.caso.numero_caso,
        "perito_id": str(designacion.usuario_id),
        "perito": designacion.usuario.nombre,
        "forma": forma,
        "texto": texto,
        "fecha": fecha.astimezone(timezone.utc).isoformat(),
    }
    canonico = json.dumps(contenido, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def firmar_acta(designacion_id, h: str) -> str:
    mensaje = f"{designacion_id}|{h}".encode("utf-8")
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), mensaje, hashlib.sha256).hexdigest()


def acta_integra(designacion) -> bool:
    """Recalcula el hash con lo guardado: si alguien tocó el texto o la fecha en la base, no coincide."""
    if not designacion.juramento_en or not designacion.juramento_hash:
        return False
    h = hash_acta(designacion, designacion.juramento_texto, designacion.juramento_en, designacion.juramento_forma)
    return h == designacion.juramento_hash and hmac.compare_digest(
        firmar_acta(designacion.id, h), designacion.juramento_firma or ""
    )


def _f(dt) -> str:
    return dt.astimezone(PERU).strftime("%d/%m/%Y %H:%M (hora de Lima)") if dt else "—"


def generar_pdf(designacion) -> bytes:
    p = designacion.pericia
    perito = designacion.usuario
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Acta de juramento {p.codigo}",
    )
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle("t", parent=estilos["Title"], fontSize=14, leading=18)
    normal = ParagraphStyle("n", parent=estilos["Normal"], fontSize=10, leading=14)
    jurado = ParagraphStyle("j", parent=normal, fontSize=11, leading=16, leftIndent=8 * mm, rightIndent=8 * mm, spaceBefore=4, spaceAfter=4)
    chico = ParagraphStyle("c", parent=normal, fontSize=8, leading=10, textColor=colors.HexColor("#555555"))

    filas = [
        ["Pericia", p.codigo],
        ["Caso", p.caso.numero_caso],
        ["Especialidad", ETIQUETA_ESPECIALIDAD.get(p.especialidad or "", p.especialidad or "—")],
        ["Disposición fiscal", designacion.documento or p.disposicion_fiscal],
        ["Perito oficial", perito.nombre],
        ["Institución / registro", " · ".join(x for x in [perito.institucion, perito.registro_profesional] if x) or "—"],
        ["Designado el", _f(designacion.designado_en)],
        ["Aceptó el cargo", _f(designacion.aceptada_en)],
        ["Prestó juramento", _f(designacion.juramento_en)],
        ["Forma", "Juramento" if designacion.juramento_forma == "juramento" else "Promesa de honor"],
    ]
    tabla = Table([[Paragraph(f"<b>{a}</b>", normal), Paragraph(str(b), normal)] for a, b in filas], colWidths=[45 * mm, 125 * mm])
    tabla.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2f5")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    integro = acta_integra(designacion)
    contenido = [
        Paragraph("ACTA DE ACEPTACIÓN DEL CARGO Y JURAMENTO DE PERITO", titulo),
        Paragraph("Código Procesal Penal (D. Leg. 957), art. 174 — CustodiaDigital", chico),
        Spacer(1, 6 * mm),
        tabla,
        Spacer(1, 6 * mm),
        Paragraph("<b>Objetivos de la pericia</b>", normal),
    ]
    contenido += [Paragraph(f"{i + 1}. {o['texto']}", normal) for i, o in enumerate(p.objetivos)]
    contenido += [
        Spacer(1, 5 * mm),
        Paragraph("<b>Texto jurado por el perito</b>", normal),
        Paragraph(f"“{designacion.juramento_texto}”", jurado),
        Spacer(1, 4 * mm),
        Paragraph(f"Firma electrónica: <b>{perito.nombre}</b> — escrita por el perito al juramentar, con su usuario de CustodiaDigital.", normal),
        Spacer(1, 8 * mm),
        Paragraph(f"SHA-256 del acta: {designacion.juramento_hash}", chico),
        Paragraph(f"Sello del servidor (HMAC-SHA256): {designacion.juramento_firma}", chico),
        Paragraph(
            "Integridad: VERIFICADA — el acta coincide con lo registrado." if integro
            else "Integridad: NO COINCIDE — el registro fue modificado después del juramento.",
            ParagraphStyle("i", parent=chico, textColor=colors.HexColor("#1b7f3b" if integro else "#b3261e")),
        ),
    ]
    doc.build(contenido)
    return buffer.getvalue()
