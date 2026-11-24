"""Sprint 8 (historia 41): ubicar firmas automáticamente.

El documento y la "firma" se DIBUJAN aquí: no se usan firmas reales (Ley 29733)."""
import math

from PIL import Image, ImageDraw, ImageFont

from app.services.ubicacion_firma_service import detectar


def _documento(con_firma=True):
    pagina = Image.new("L", (1240, 1754), 255)
    d = ImageDraw.Draw(pagina)
    letra = ImageFont.load_default(size=26)
    for i in range(14):
        d.text((100, 200 + i * 42), "El vendedor transfiere el vehiculo de placa ABC-123 al comprador.", font=letra, fill=0)
    d.line((680, 1360, 1100, 1360), fill=0, width=2)  # raya donde se firma
    d.text((760, 1375), "Firma del comprador", font=letra, fill=0)
    if con_firma:  # trazo manuscrito: una curva con rulos
        puntos = [(720 + t * 3.2, 1290 - 45 * math.sin(t / 9) - 25 * math.cos(t / 3)) for t in range(110)]
        d.line(puntos, fill=0, width=6, joint="curve")
    return pagina


def _dentro(c, x, y):
    return c["x"] <= x <= c["x"] + c["ancho"] and c["y"] <= y <= c["y"] + c["alto"]


def test_encuentra_la_firma_y_no_el_texto():
    r = detectar(_documento())
    assert r["candidatos"], "debe sugerir al menos una zona"
    mejor = r["candidatos"][0]
    assert _dentro(mejor, 900 / 1240, 1290 / 1754), "la zona sugerida debe contener la firma"
    assert not any(_dentro(c, 600 / 1240, 400 / 1754) for c in r["candidatos"]), "el texto impreso no es firma"


def test_documento_sin_firma_no_sugiere_nada():
    assert detectar(_documento(con_firma=False))["candidatos"] == []
