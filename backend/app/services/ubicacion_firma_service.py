"""Sprint 8 (historia 41): ubicar firmas automáticamente en un documento.

Idea: en una página escaneada hay texto impreso, líneas y firmas. El OCR (Tesseract, el mismo
de la HU29) dice dónde está el texto impreso; eso se borra. También se borran las líneas rectas
(la raya "_______" donde se firma). Lo que queda con forma de trazo a mano es candidato a firma.
Si cerca hay una palabra como "Firma" o "Firmado", el candidato sube de puntaje.

Solo SUGIERE zonas: el perito confirma o corrige el rectángulo antes de analizar (HU30).
Todo corre dentro del servidor: la página no sale del laboratorio.
"""
import re
import subprocess
import tempfile
import unicodedata
from typing import Dict, List

import cv2
import numpy as np
from PIL import Image

from app.core.config import settings

ANCHO_TRABAJO = 1600        # se trabaja con la página a este ancho (proporciones iguales)
MAX_CANDIDATOS = 4
CONFIANZA_TEXTO = 55        # palabras OCR con al menos esta confianza se tratan como texto impreso
PALABRAS_FIRMA = ("firma", "firmado", "firmada", "suscrito", "suscrita", "conforme", "signature", "rubrica")


def _normal(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", sin_tildes.lower())


def _palabras_ocr(gris: np.ndarray) -> List[Dict]:
    """Cajas de las palabras que Tesseract lee con buena confianza (texto impreso)."""
    with tempfile.NamedTemporaryFile(prefix="firma_", suffix=".png") as tmp:
        cv2.imwrite(tmp.name, gris)
        try:
            r = subprocess.run(
                ["tesseract", tmp.name, "stdout", "-l", settings.OCR_IDIOMA, "--psm", "11", "tsv"],
                capture_output=True, text=True, timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []  # Tesseract no instalado o colgado
    if r.returncode != 0:
        return []  # sin OCR se sigue: solo se pierde el borrado del texto impreso
    palabras = []
    for fila in r.stdout.splitlines()[1:]:
        c = fila.split("\t")
        if len(c) < 12 or c[0] != "5":
            continue
        texto = c[11].strip()
        conf = float(c[10])
        x, y, w, h = (int(v) for v in c[6:10])
        if texto and conf >= CONFIANZA_TEXTO and sum(ch.isalnum() for ch in texto) >= 2:
            palabras.append({"texto": texto, "x": x, "y": y, "w": w, "h": h})
    return palabras


def _borrar_lineas(tinta: np.ndarray) -> np.ndarray:
    """Quita las rayas horizontales largas y DELGADAS (la línea "______" donde se firma,
    subrayados, bordes de tabla). Un trazo grueso de la firma no se toca."""
    alto, ancho = tinta.shape
    horizontales = cv2.morphologyEx(tinta, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(40, ancho // 8), 1)))
    n, etiquetas, stats, _ = cv2.connectedComponentsWithStats(horizontales)
    grosor_max = max(4, int(alto * 0.004))
    delgadas = np.isin(etiquetas, [i for i in range(1, n) if stats[i, cv2.CC_STAT_HEIGHT] <= grosor_max])
    salida = tinta.copy()
    salida[cv2.dilate(delgadas.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0] = 0
    return salida


def _irregularidad(recorte: np.ndarray) -> float:
    """Qué tan "a mano" es la tinta: las firmas tienen trazos curvos y largos (mucho contorno
    para poca área); el texto impreso borrado o las manchas, no. Devuelve 0..1."""
    contornos, _ = cv2.findContours(recorte, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contornos:
        return 0.0
    perimetro = sum(cv2.arcLength(c, True) for c in contornos)
    area = max(1.0, float(cv2.countNonZero(recorte)))
    return float(min(1.0, (perimetro / area) / 0.6))


def detectar(imagen: Image.Image) -> Dict:
    """Busca zonas con firma en una página. Devuelve candidatos con coordenadas en fracciones
    de la página (x, y, ancho, alto entre 0 y 1), igual que el recorte manual de la HU30."""
    original = np.array(imagen.convert("L"))
    escala = ANCHO_TRABAJO / original.shape[1]
    # Siempre al mismo ancho: así los tamaños mínimos y la "unión" de trazos valen igual para
    # una página escaneada grande que para una foto chica de una sola firma.
    gris = cv2.resize(original, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA if escala < 1 else cv2.INTER_CUBIC)
    gris = cv2.medianBlur(gris, 3)  # quita el "polvo" del escaneo sin borrar trazos
    alto, ancho = gris.shape

    _, tinta = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    palabras = _palabras_ocr(gris)
    for p in palabras:  # borra el texto impreso
        cv2.rectangle(tinta, (p["x"] - 2, p["y"] - 2), (p["x"] + p["w"] + 2, p["y"] + p["h"] + 2), 0, -1)
    tinta = _borrar_lineas(tinta)
    tinta = cv2.morphologyEx(tinta, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))  # polvo del escaneo

    # Une los trazos cercanos de una misma firma en un solo bloque.
    unir = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (max(15, ancho // 45), max(11, alto // 70)))
    bloques = cv2.dilate(tinta, unir)
    n, _, stats, _ = cv2.connectedComponentsWithStats(bloques)

    claves = [p for p in palabras if any(_normal(p["texto"]).startswith(k) for k in PALABRAS_FIRMA)]
    candidatos = []
    for i in range(1, n):
        x, y, w, h, _ = stats[i]
        if w < ancho * 0.06 or h < alto * 0.03 or w * h < ancho * alto * 0.003:
            continue  # muy chico o muy bajo: letra suelta, mancha, resto de una línea de texto
        recorte = tinta[y:y + h, x:x + w]
        densidad = cv2.countNonZero(recorte) / float(w * h)
        if not 0.01 <= densidad <= 0.45 or not 0.6 <= w / h <= 12:
            continue  # bloque casi vacío, mancha sólida (sello relleno) o tira de ruido
        # El texto impreso que el OCR no leyó queda como muchas letras sueltas de igual tamaño;
        # una firma son pocos trazos grandes.
        piezas, _, st, _ = cv2.connectedComponentsWithStats(recorte)
        areas = sorted(st[1:, cv2.CC_STAT_AREA], reverse=True)
        if piezas > 12 and sum(areas[:3]) < 0.5 * sum(areas):
            continue
        puntaje = 0.55 * _irregularidad(recorte) + 0.15 * min(1.0, w / (ancho * 0.25))
        motivo = "trazo manuscrito"
        # Una palabra "Firma..." justo debajo, encima o a la izquierda del bloque lo confirma.
        for c in claves:
            cerca_x = c["x"] < x + w + ancho * 0.05 and c["x"] + c["w"] > x - ancho * 0.25
            cerca_y = -alto * 0.06 < c["y"] - (y + h) < alto * 0.08 or abs(c["y"] - y) < h
            if cerca_x and cerca_y:
                puntaje += 0.3
                motivo = f"trazo manuscrito junto a «{c['texto']}»"
                break
        margen_x, margen_y = int(w * 0.06) + 4, int(h * 0.12) + 4
        x0, y0 = max(0, x - margen_x), max(0, y - margen_y)
        x1, y1 = min(ancho, x + w + margen_x), min(alto, y + h + margen_y)
        candidatos.append({
            "x": round(x0 / ancho, 4), "y": round(y0 / alto, 4),
            "ancho": round((x1 - x0) / ancho, 4), "alto": round((y1 - y0) / alto, 4),
            "puntaje": round(min(1.0, puntaje), 3), "motivo": motivo,
        })

    candidatos.sort(key=lambda c: c["puntaje"], reverse=True)
    return {
        "candidatos": candidatos[:MAX_CANDIDATOS],
        "texto_borrado": len(palabras),
        "nota": "Zonas sugeridas automáticamente: confirma o corrige el rectángulo antes de analizar.",
    }
