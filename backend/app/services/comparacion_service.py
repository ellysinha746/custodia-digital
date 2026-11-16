"""Sprint 7 (historia 31): comparación del texto de dos versiones de un documento.

Se compara palabra por palabra (difflib). Para no confundir ruido del OCR con cambios reales,
al EMPAREJAR se ignoran mayúsculas y tildes ("Pérez" = "PEREZ"); pero los cambios se muestran
con el texto tal como se leyó. Las cifras (montos, fechas, DNI, cuentas) se listan aparte:
en un documento alterado suelen ser lo que cambió.
"""
import re
import unicodedata
from difflib import SequenceMatcher

PALABRA = re.compile(r"\S+")


def _normal(palabra: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", palabra).encode("ascii", "ignore").decode()
    return sin_tildes.casefold().strip(".,;:()[]\"'«»")


def _tiene_cifra(texto: str) -> bool:
    return any(c.isdigit() for c in texto)


def comparar(texto_a: str, texto_b: str) -> dict:
    """Segmentos con el texto común y los cambios, más un resumen y las cifras cambiadas."""
    a = PALABRA.findall((texto_a or "").replace("\f", "\n"))
    b = PALABRA.findall((texto_b or "").replace("\f", "\n"))
    m = SequenceMatcher(None, [_normal(x) for x in a], [_normal(x) for x in b], autojunk=False)

    segmentos, cifras, cambios = [], [], 0
    for op, i1, i2, j1, j2 in m.get_opcodes():
        antes, despues = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        # El OCR a veces parte o junta palabras ("J uan" / "Juan", "15,000. 00"): si es el mismo
        # texto sin espacios, no es un cambio del documento.
        if op == "replace" and _normal("".join(a[i1:i2])) == _normal("".join(b[j1:j2])):
            op = "equal"
        if op == "equal":
            segmentos.append({"tipo": "igual", "texto": antes, "palabras": i2 - i1})
            continue
        cambios += 1
        tipo = {"replace": "cambiado", "delete": "eliminado", "insert": "agregado"}[op]
        segmentos.append({"tipo": tipo, "antes": antes, "despues": despues})
        if _tiene_cifra(antes) or _tiene_cifra(despues):
            cifras.append({"antes": antes or None, "despues": despues or None})

    similitud = round(m.ratio() * 100, 1) if (a or b) else 100.0
    return {
        "segmentos": segmentos,
        "cifras_cambiadas": cifras,
        "cambios": cambios,
        "palabras_a": len(a),
        "palabras_b": len(b),
        "similitud": similitud,
    }
