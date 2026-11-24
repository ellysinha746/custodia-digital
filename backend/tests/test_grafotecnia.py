"""Sprint 8 (historia 37): pruebas del cotejo de texto (HU31) y del análisis de firmas (HU30).

Las firmas se DIBUJAN aquí mismo: no se usa ninguna firma real (Ley 29733)."""
import numpy as np
from PIL import Image, ImageDraw

from app.services import comparacion_service, firma_service


def test_cotejo_detecta_monto_cambiado():
    r = comparacion_service.comparar(
        "El comprador pagará S/ 15,000 el 10 de marzo.",
        "El comprador pagará S/ 75,000 el 10 de marzo.",
    )
    assert r["cambios"] == 1
    assert r["cifras_cambiadas"] == [{"antes": "15,000", "despues": "75,000"}]


def test_cotejo_ignora_tildes_y_mayusculas_del_ocr():
    r = comparacion_service.comparar("Juan Pérez firmó", "JUAN PEREZ firmó")
    assert r["cambios"] == 0


def _firma(trazos, inclinacion=0):
    img = Image.new("L", (400, 160), 255)
    d = ImageDraw.Draw(img)
    for t in trazos:
        d.line([(x + inclinacion * (160 - y) / 160, y) for x, y in t], fill=0, width=5)
    return {"id": str(len(trazos)) + str(inclinacion), "nombre": "dibujo", "firma": firma_service.preparar(img)}


AUTOR = [[(40, 120), (80, 30), (120, 120), (160, 40), (220, 110), (300, 50), (360, 100)]]


def test_firma_identica_se_parece_mas_que_una_distinta():
    a, b = _firma(AUTOR), _firma(AUTOR)
    otra = _firma([[(40, 40), (360, 40)], [(200, 20), (200, 140)]])
    igual = firma_service.comparar(a["firma"], b["firma"])
    distinta = firma_service.comparar(a["firma"], otra["firma"])
    assert igual["superposicion"] > distinta["superposicion"]


def test_analisis_completo_y_hash_reproducible():
    patrones = [_firma(AUTOR, i) for i in (0, 6, 12)]
    resultado = firma_service.analizar(_firma(AUTOR, 40), patrones)
    assert len(resultado["resumen"]) == 4
    assert all(m["estado"] in ("dentro", "limite", "fuera") for m in resultado["resumen"])
    # El hash no depende de las imágenes y se puede recalcular igual.
    assert firma_service.hash_resultado(resultado) == firma_service.hash_resultado(resultado)
    assert isinstance(resultado["comparaciones"][0]["superposicion_png"], str)


def test_aviso_con_pocos_patrones():
    resultado = firma_service.analizar(_firma(AUTOR, 30), [_firma(AUTOR, 0), _firma(AUTOR, 8)])
    assert resultado["avisos"], "con 2 patrones debe avisar que se recomiendan 3 o más"
