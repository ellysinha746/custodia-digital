"""Sprint 7 (historia 30): análisis comparativo de firmas con OpenCV.

El perito elige UNA firma dubitada (la cuestionada) y DOS O MÁS indubitadas (patrones de
autoría conocida), y si hace falta marca con un rectángulo dónde está la firma en cada página.
El sistema:

1. Prepara cada firma: escala de grises, binarización (Otsu), quita manchas pequeñas, recorta
   al contorno de la tinta y lleva todas a la misma altura.
2. Mide cada firma: proporción ancho/alto, densidad de tinta, inclinación, trazos separados.
3. Compara la dubitada con cada patrón: superposición de trazos, diferencia de forma (momentos
   de Hu), puntos característicos coincidentes (ORB) y similitud estructural (SSIM).
4. Calcula el RANGO NATURAL DEL AUTOR comparando los patrones entre sí: ninguna persona firma
   dos veces igual, así que lo relevante es si la dubitada cae dentro o fuera de esa variación.
5. Genera una imagen superpuesta: negro = trazo en ambas, azul = solo en la dubitada,
   naranja = solo en el patrón.

El sistema MIDE; nunca dictamina autenticidad. Concluye el perito grafotécnico.
Todo se calcula en el servidor (nada sale del laboratorio) y es reproducible: mismas
imágenes y mismos recortes dan el mismo resultado.
"""
import base64
import hashlib
import json
import math
from itertools import combinations
from typing import Dict, List, Optional

import cv2
import numpy as np
from PIL import Image

ALTO = 220          # altura común a la que se llevan las firmas
TOLERANCIA = 0.20   # zona límite: hasta 20 % más allá de la variación de los patrones
MIN_PATRONES_RECOMENDADO = 3
MOTOR = f"OpenCV {cv2.__version__}"

# Métricas de comparación. "mayor": True = un valor más alto indica más parecido.
COMPARACIONES = {
    "superposicion": {"etiqueta": "Superposición de trazos", "mayor": True, "formato": "porcentaje"},
    "puntos_coincidentes": {"etiqueta": "Puntos característicos coincidentes (ORB)", "mayor": True, "formato": "porcentaje"},
    "similitud_estructural": {"etiqueta": "Similitud estructural (SSIM)", "mayor": True, "formato": "decimal"},
    "diferencia_forma": {"etiqueta": "Diferencia de forma (momentos de Hu)", "mayor": False, "formato": "decimal"},
}
MEDIDAS = {
    "proporcion": "Proporción ancho / alto",
    "densidad": "Densidad de tinta",
    "inclinacion": "Inclinación (grados)",
    "trazos": "Trazos separados",
}


# ---------------------------------------------------------------- preparación

def recortar(imagen: Image.Image, recorte: Optional[Dict]) -> Image.Image:
    """recorte = {x, y, ancho, alto} en fracciones de 0 a 1 de la página. None = página completa."""
    if not recorte:
        return imagen
    w, h = imagen.size
    x0 = max(0, int(recorte["x"] * w))
    y0 = max(0, int(recorte["y"] * h))
    x1 = min(w, int((recorte["x"] + recorte["ancho"]) * w))
    y1 = min(h, int((recorte["y"] + recorte["alto"]) * h))
    if x1 - x0 < 10 or y1 - y0 < 10:
        raise ValueError("El recorte es demasiado pequeño.")
    return imagen.crop((x0, y0, x1, y1))


def preparar(imagen: Image.Image) -> np.ndarray:
    """Firma binaria (tinta = 255) recortada a la tinta y llevada a ALTO píxeles de alto."""
    gris = np.array(imagen.convert("L"))
    gris = cv2.GaussianBlur(gris, (5, 5), 0)
    _, binaria = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Sprint 8 (historia 41): quitar la raya recta donde se firma ("________"). Solo líneas
    # perfectamente horizontales, delgadas y que cruzan más del 60 % del recorte: un trazo
    # de la firma, aunque sea largo, no es tan recto ni tan delgado.
    lineas = cv2.morphologyEx(binaria, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, int(binaria.shape[1] * 0.6)), 1)))
    n, etiquetas, stats, _ = cv2.connectedComponentsWithStats(lineas, 8)
    grosor_max = max(3, int(binaria.shape[0] * 0.03))
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_HEIGHT] <= grosor_max:
            binaria[cv2.dilate((etiquetas == i).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0] = 0

    # Quitar manchas pequeñas (polvo, textura del papel).
    n, etiquetas, stats, _ = cv2.connectedComponentsWithStats(binaria, 8)
    area_minima = max(20, int(0.0005 * binaria.size))
    limpia = np.zeros_like(binaria)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= area_minima:
            limpia[etiquetas == i] = 255

    ys, xs = np.nonzero(limpia)
    if len(xs) == 0:
        raise ValueError("No se encontró tinta en el recorte.")
    firma = limpia[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    alto, ancho = firma.shape
    escala = ALTO / alto
    firma = cv2.resize(firma, (max(1, int(ancho * escala)), ALTO), interpolation=cv2.INTER_AREA)
    _, firma = cv2.threshold(firma, 127, 255, cv2.THRESH_BINARY)
    return firma


# ---------------------------------------------------------------- medidas de una firma

def medir(firma: np.ndarray) -> Dict:
    alto, ancho = firma.shape
    m = cv2.moments(firma, binaryImage=True)
    # Inclinación del eje principal respecto de la vertical (negativo = hacia la derecha).
    inclinacion = math.degrees(math.atan2(m["mu11"], m["mu02"])) if m["mu02"] else 0.0
    n, _, _, _ = cv2.connectedComponentsWithStats(firma, 8)
    return {
        "proporcion": round(ancho / alto, 3),
        "densidad": round(float(np.count_nonzero(firma)) / (ancho * alto), 3),
        "inclinacion": round(inclinacion, 1),
        "trazos": int(n - 1),
    }


# ---------------------------------------------------------------- comparación de dos firmas

def _mismo_lienzo(a: np.ndarray, b: np.ndarray):
    ancho = max(a.shape[1], b.shape[1])

    def centrar(x):
        lienzo = np.zeros((ALTO, ancho), np.uint8)
        desde = (ancho - x.shape[1]) // 2
        lienzo[:, desde:desde + x.shape[1]] = x
        return lienzo

    return centrar(a), centrar(b)


def _ssim(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    k, s = (11, 11), 1.5
    mu1, mu2 = cv2.GaussianBlur(a, k, s), cv2.GaussianBlur(b, k, s)
    s1 = cv2.GaussianBlur(a * a, k, s) - mu1 ** 2
    s2 = cv2.GaussianBlur(b * b, k, s) - mu2 ** 2
    s12 = cv2.GaussianBlur(a * b, k, s) - mu1 * mu2
    mapa = ((2 * mu1 * mu2 + c1) * (2 * s12 + c2)) / ((mu1 ** 2 + mu2 ** 2 + c1) * (s1 + s2 + c2))
    return float(mapa.mean())


def _orb(a: np.ndarray, b: np.ndarray) -> float:
    orb = cv2.ORB_create(500)
    ka, da = orb.detectAndCompute(a, None)
    kb, db = orb.detectAndCompute(b, None)
    if da is None or db is None or not ka or not kb:
        return 0.0
    pares = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(da, db, k=2)
    buenos = [p[0] for p in pares if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
    return len(buenos) / min(len(ka), len(kb))


def comparar(a: np.ndarray, b: np.ndarray) -> Dict:
    A, B = _mismo_lienzo(a, b)
    nucleo = np.ones((5, 5), np.uint8)
    Ad, Bd = cv2.dilate(A, nucleo), cv2.dilate(B, nucleo)  # tolera pequeños corrimientos del trazo
    union = np.logical_or(Ad > 0, Bd > 0).sum()
    inter = np.logical_and(Ad > 0, Bd > 0).sum()
    borroso = lambda x: cv2.GaussianBlur(x, (9, 9), 0)
    return {
        "superposicion": round(float(inter / union) if union else 0.0, 3),
        "puntos_coincidentes": round(_orb(A, B), 3),
        "similitud_estructural": round(_ssim(borroso(A), borroso(B)), 3),
        "diferencia_forma": round(float(cv2.matchShapes(a, b, cv2.CONTOURS_MATCH_I2, 0)), 4),
    }


def superponer_png(a: np.ndarray, b: np.ndarray) -> str:
    """PNG en base64: negro = ambas, azul = solo dubitada (a), naranja = solo patrón (b)."""
    A, B = _mismo_lienzo(a, b)
    imagen = np.full(A.shape + (3,), 255, np.uint8)
    ea, eb = A > 0, B > 0
    imagen[ea & ~eb] = (230, 120, 0)   # BGR: azul
    imagen[eb & ~ea] = (0, 140, 255)   # BGR: naranja
    imagen[ea & eb] = (40, 40, 40)
    ok, png = cv2.imencode(".png", imagen)
    return base64.b64encode(png.tobytes()).decode()


def miniatura_png(firma: np.ndarray) -> str:
    ok, png = cv2.imencode(".png", 255 - firma)  # tinta negra sobre blanco
    return base64.b64encode(png.tobytes()).decode()


# ---------------------------------------------------------------- análisis completo

def analizar(dubitada: Dict, indubitadas: List[Dict]) -> Dict:
    """dubitada / indubitadas: {"id", "nombre", "firma": np.ndarray}. Devuelve un resultado
    serializable (con imágenes en base64)."""
    # 1) Rango natural del autor: patrones comparados entre sí.
    entre_patrones = [comparar(x["firma"], y["firma"]) for x, y in combinations(indubitadas, 2)]
    rango = {}
    for clave in COMPARACIONES:
        valores = [c[clave] for c in entre_patrones]
        rango[clave] = {"min": min(valores), "max": max(valores)}

    # 2) Dubitada contra cada patrón.
    comparaciones = []
    for patron in indubitadas:
        valores = comparar(dubitada["firma"], patron["firma"])
        comparaciones.append({
            "indubitada_id": patron["id"],
            "indubitada": patron["nombre"],
            "valores": valores,
            "superposicion_png": superponer_png(dubitada["firma"], patron["firma"]),
        })

    # 3) ¿El promedio de la dubitada cae dentro de la variación natural del autor?
    resumen = []
    for clave, info in COMPARACIONES.items():
        promedio = round(sum(c["valores"][clave] for c in comparaciones) / len(comparaciones), 3)
        r = rango[clave]
        # dentro: tan parecida como los patrones entre sí; limite: hasta TOLERANCIA más allá;
        # fuera: más diferente de lo que el autor varía naturalmente.
        if info["mayor"]:
            estado = "dentro" if promedio >= r["min"] else "limite" if promedio >= r["min"] * (1 - TOLERANCIA) else "fuera"
        else:
            estado = "dentro" if promedio <= r["max"] else "limite" if promedio <= r["max"] * (1 + TOLERANCIA) else "fuera"
        resumen.append({
            "clave": clave,
            "etiqueta": info["etiqueta"],
            "formato": info["formato"],
            "mayor_es_mas_parecido": info["mayor"],
            "dubitada_promedio": promedio,
            "rango_autor": r,
            "estado": estado,
        })

    firmas = [
        {"id": f["id"], "nombre": f["nombre"], "rol": rol, "medidas": medir(f["firma"]),
         "miniatura_png": miniatura_png(f["firma"])}
        for rol, f in [("dubitado", dubitada)] + [("indubitado", x) for x in indubitadas]
    ]
    avisos = []
    if len(indubitadas) < MIN_PATRONES_RECOMENDADO:
        avisos.append(
            f"Con {len(indubitadas)} patrones la variación natural del autor se estima con poca base: "
            f"se recomiendan {MIN_PATRONES_RECOMENDADO} o más firmas indubitadas."
        )
    return {
        "motor": MOTOR,
        "avisos": avisos,
        "firmas": firmas,
        "medidas_etiquetas": MEDIDAS,
        "comparaciones": comparaciones,
        "resumen": resumen,
        "metricas_fuera_de_rango": sum(1 for r in resumen if r["estado"] == "fuera"),
        "metricas_en_limite": sum(1 for r in resumen if r["estado"] == "limite"),
        "nota": (
            "Medición automática de apoyo. Compara la firma dubitada con la variación natural que muestran "
            "los patrones indubitados entre sí. No dictamina autenticidad: la conclusión corresponde al "
            "perito grafotécnico."
        ),
    }


def hash_resultado(resultado: Dict) -> str:
    """SHA-256 del resultado sin imágenes (para comprobar después que nadie lo tocó)."""
    sin_imagenes = json.loads(json.dumps(resultado))
    for f in sin_imagenes.get("firmas", []):
        f.pop("miniatura_png", None)
    for c in sin_imagenes.get("comparaciones", []):
        c.pop("superposicion_png", None)
    canonico = json.dumps(sin_imagenes, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()
