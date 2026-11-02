import csv
import hashlib
import hmac
import io
import json
from datetime import datetime, timezone
from typing import List, Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from app.core.config import settings

# Sprint 4 (historia 16): reporte de auditoría con sello de tiempo.
#
# El "sello" tiene tres partes:
#   1. fecha y hora UTC exactas de emisión,
#   2. hash SHA-256 de los eventos incluidos (si alguien edita una fila, cambia),
#   3. firma HMAC-SHA256 con la clave del servidor sobre folio + fecha + hash.
# Además se guarda el SHA-256 del archivo entregado: subiendo el archivo a
# "Verificar reporte" se comprueba que es auténtico y que no fue modificado.

ETIQUETA_ACCION = {
    "subida": "Subida",
    "acceso": "Acceso",
    "descarga": "Descarga",
    "verificacion": "Verificación",
}


def hash_contenido(eventos: List[Dict]) -> str:
    canonico = json.dumps(eventos, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def firmar(folio: str, generado_en: datetime, hash_eventos: str) -> str:
    # Se normaliza a UTC para que la firma no dependa de la zona horaria de la base.
    fecha = generado_en.astimezone(timezone.utc).isoformat()
    mensaje = f"{folio}|{fecha}|{hash_eventos}".encode("utf-8")
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), mensaje, hashlib.sha256).hexdigest()


def firma_valida(folio: str, generado_en: datetime, hash_eventos: str, firma: str) -> bool:
    return hmac.compare_digest(firmar(folio, generado_en, hash_eventos), firma)


def _fecha_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M:%S UTC")


def generar_csv(eventos: List[Dict], meta: Dict) -> bytes:
    salida = io.StringIO()
    w = csv.writer(salida)
    w.writerow(["REPORTE DE AUDITORÍA - CADENA DE CUSTODIA DIGITAL"])
    w.writerow(["folio", meta["folio"]])
    w.writerow(["generado_por", meta["generado_por"]])
    w.writerow(["filtro_accion", meta["filtro"] or "todas"])
    w.writerow(["total_eventos", len(eventos)])
    w.writerow([])
    w.writerow(["fecha_utc", "accion", "resultado", "usuario", "caso", "archivo"])
    for e in eventos:
        w.writerow([e["fecha"], e["accion"], e["resultado"] or "", e["usuario"], e["caso"], e["archivo"]])
    w.writerow([])
    w.writerow(["SELLO DE TIEMPO"])
    w.writerow(["fecha_emision_utc", meta["generado_en"].isoformat()])
    w.writerow(["sha256_eventos", meta["hash_contenido"]])
    w.writerow(["firma_hmac_sha256", meta["firma"]])
    return ("﻿" + salida.getvalue()).encode("utf-8")


def generar_pdf(eventos: List[Dict], meta: Dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=18 * mm,
        title=f"Reporte de auditoría {meta['folio']}",
        author="CustodiaDigital",
    )
    estilos = getSampleStyleSheet()
    celda = ParagraphStyle("celda", parent=estilos["BodyText"], fontSize=7.5, leading=9)
    mono = ParagraphStyle("mono", parent=celda, fontName="Courier", fontSize=7.5)

    fecha_txt = _fecha_utc(meta["generado_en"])
    historia = [
        Paragraph("Reporte de auditoría · Cadena de custodia digital", estilos["Title"]),
        Paragraph(
            f"<b>Folio:</b> {meta['folio']} &nbsp;&nbsp; <b>Emitido:</b> {fecha_txt} &nbsp;&nbsp; "
            f"<b>Por:</b> {meta['generado_por']} &nbsp;&nbsp; <b>Filtro:</b> {meta['filtro'] or 'todas las acciones'} "
            f"&nbsp;&nbsp; <b>Eventos:</b> {len(eventos)}",
            estilos["BodyText"],
        ),
        Spacer(1, 6 * mm),
    ]

    filas = [["Fecha (UTC)", "Acción", "Resultado", "Usuario", "Caso", "Archivo"]]
    for e in eventos:
        filas.append([
            Paragraph(e["fecha"].replace("T", " ")[:19], mono),
            Paragraph(ETIQUETA_ACCION.get(e["accion"], e["accion"]), celda),
            Paragraph(e["resultado"] or "—", mono),
            Paragraph(e["usuario"], celda),
            Paragraph(e["caso"], mono),
            Paragraph(e["archivo"], celda),
        ])
    if len(filas) == 1:
        filas.append(["—", "Sin eventos para este filtro", "", "", "", ""])

    tabla = Table(filas, colWidths=[38 * mm, 26 * mm, 38 * mm, 40 * mm, 32 * mm, None], repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0E2A33")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F7")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9D3D8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    historia.append(tabla)
    historia.append(Spacer(1, 8 * mm))

    sello = Table(
        [
            [Paragraph("<b>SELLO DE TIEMPO</b>", celda), ""],
            [Paragraph("Fecha de emisión (UTC)", celda), Paragraph(meta["generado_en"].isoformat(), mono)],
            [Paragraph("SHA-256 de los eventos", celda), Paragraph(meta["hash_contenido"], mono)],
            [Paragraph("Firma HMAC-SHA256", celda), Paragraph(meta["firma"], mono)],
            [Paragraph(
                "Para comprobar la autenticidad, sube este archivo en Auditoría → Verificar reporte. "
                "Cualquier modificación del archivo invalida la verificación.", celda), ""],
        ],
        colWidths=[50 * mm, None],
    )
    sello.setStyle(TableStyle([
        ("SPAN", (0, 0), (1, 0)),
        ("SPAN", (0, 4), (1, 4)),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#0E7490")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0F2F7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    historia.append(sello)

    def pie(canvas, documento):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#55666E"))
        canvas.drawString(
            14 * mm, 9 * mm,
            f"CustodiaDigital · Folio {meta['folio']} · Emitido {fecha_txt} · Sello {meta['firma'][:16]}…",
        )
        canvas.drawRightString(landscape(A4)[0] - 14 * mm, 9 * mm, f"Página {documento.page}")
        canvas.restoreState()

    doc.build(historia, onFirstPage=pie, onLaterPages=pie)
    return buffer.getvalue()