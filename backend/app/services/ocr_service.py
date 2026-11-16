"""Sprint 7 (historia 29): texto de documentos escaneados (OCR) con Tesseract, DENTRO del servidor.

Ningún documento sale del laboratorio. Para cada página:
- PDF con capa de texto (generado por computadora): se usa ese texto tal cual (`pdftotext`).
- PDF escaneado o imagen: se rasteriza y se lee con `tesseract ... tsv`, que además da la
  confianza de cada palabra (0-100). El promedio se muestra para saber cuánto fiarse.

El OCR lee texto impreso; con letra manuscrita y firmas es poco fiable (no "lee" firmas).
Se lee la COPIA DE TRABAJO: el original no se toca.
"""
import subprocess
import tempfile
from datetime import datetime, timezone
from functools import lru_cache
from statistics import mean
from uuid import UUID

from fastapi import HTTPException
from PIL import Image

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.archivo import Archivo
from app.models.log_custodia import LogCustodia, AccionEnum
from app.services import vista_service

MIN_CARACTERES_CAPA = 25  # menos que esto en una página del PDF → se considera escaneada


@lru_cache
def version_tesseract() -> str:
    try:
        salida = subprocess.run(["tesseract", "--version"], capture_output=True, text=True, timeout=10).stdout
        return salida.splitlines()[0].strip()  # "tesseract 5.5.0"
    except Exception:
        return "tesseract"


def _preparar(imagen: Image.Image) -> Image.Image:
    """Gris y, si la imagen es chica (foto de celular recortada), se amplía: Tesseract
    funciona mejor con letras de ~30 px de alto."""
    imagen = imagen.convert("L")
    if imagen.width < 1500:
        factor = 2 if imagen.width >= 750 else 3
        imagen = imagen.resize((imagen.width * factor, imagen.height * factor), Image.LANCZOS)
    return imagen


def _tesseract(imagen: Image.Image) -> tuple:
    """(texto con saltos de línea y párrafos, lista de confianzas por palabra)."""
    with tempfile.NamedTemporaryFile(prefix="ocr_", suffix=".png") as tmp:
        _preparar(imagen).save(tmp.name, format="PNG")
        r = subprocess.run(
            ["tesseract", tmp.name, "stdout", "-l", settings.OCR_IDIOMA, "--psm", "3", "tsv"],
            capture_output=True, text=True, timeout=300,
        )
    if r.returncode != 0:
        raise RuntimeError(f"tesseract falló: {r.stderr.strip()[:200]}")
    lineas, confianzas = {}, []
    for fila in r.stdout.splitlines()[1:]:
        c = fila.split("\t")
        if len(c) < 12 or c[0] != "5" or not c[11].strip():
            continue  # solo palabras (nivel 5) con texto
        bloque, parrafo, linea = int(c[2]), int(c[3]), int(c[4])
        lineas.setdefault((bloque, parrafo, linea), []).append(c[11])
        if float(c[10]) >= 0:
            confianzas.append(float(c[10]))
    partes, anterior = [], None
    for (bloque, parrafo, linea), palabras in lineas.items():
        if anterior and anterior != (bloque, parrafo):
            partes.append("")  # línea en blanco entre párrafos
        partes.append(" ".join(palabras))
        anterior = (bloque, parrafo)
    return "\n".join(partes), confianzas


def _capa_de_texto(ruta_pdf: str, paginas: int) -> list:
    r = subprocess.run(
        ["pdftotext", "-f", "1", "-l", str(paginas), "-layout", "-enc", "UTF-8", ruta_pdf, "-"],
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        return [""] * paginas
    textos = r.stdout.split("\f")
    return [(textos[i] if i < len(textos) else "").rstrip() for i in range(paginas)]


def leer_texto(archivo: Archivo) -> dict:
    """Extrae el texto de todas las páginas (hasta OCR_MAX_PAGINAS). Lanza excepción si no puede."""
    return leer_texto_de(archivo.ruta_copia_trabajo, vista_service.tipo_visual(archivo))


def leer_texto_de(ruta_almacen: str, tipo: str = None) -> dict:
    """Igual que leer_texto, para cualquier ruta del almacenamiento (p. ej. una versión observada,
    historia 31). Si no se indica el tipo, se detecta por el contenido."""
    textos, confianzas, usados = [], [], set()
    with vista_service.copia_local(ruta_almacen) as ruta:
        tipo = tipo or vista_service.tipo_por_contenido(ruta)
        if not tipo:
            raise HTTPException(status_code=415, detail="Solo se puede leer el texto de imágenes y PDFs.")
        if tipo == "pdf":
            total = vista_service.paginas_pdf(ruta)
            n = min(total, settings.OCR_MAX_PAGINAS)
            capa = _capa_de_texto(ruta, n)
            for i in range(n):
                if len(capa[i].strip()) >= MIN_CARACTERES_CAPA:
                    textos.append(capa[i])
                    usados.add("capa de texto del PDF")
                else:
                    imagen, _ = vista_service.imagen_de_pagina(ruta, "pdf", i + 1, dpi=settings.OCR_DPI)
                    texto, conf = _tesseract(imagen)
                    textos.append(texto)
                    confianzas.extend(conf)
                    usados.add(f"{version_tesseract()} ({settings.OCR_IDIOMA})")
        else:
            imagen, total = vista_service.imagen_de_pagina(ruta, "imagen", 1)
            n = min(total, settings.OCR_MAX_PAGINAS)
            for i in range(n):
                if i:
                    imagen, _ = vista_service.imagen_de_pagina(ruta, "imagen", i + 1)
                texto, conf = _tesseract(imagen)
                textos.append(texto)
                confianzas.extend(conf)
            usados.add(f"{version_tesseract()} ({settings.OCR_IDIOMA})")
    return {
        "texto": "\f".join(textos),
        "confianza": round(mean(confianzas), 1) if confianzas else None,
        "paginas": n,
        "paginas_total": total,
        "motor": " + ".join(sorted(usados)),
    }


def preparar(archivo: Archivo) -> bool:
    """Marca el archivo como pendiente de OCR si es imagen o PDF. Devuelve si aplica (no hace commit)."""
    if not vista_service.tipo_visual(archivo):
        return False
    archivo.ocr_estado = "pendiente"
    archivo.ocr_error = None
    return True


def procesar(archivo_id: UUID, usuario_id: UUID) -> None:
    """Corre en segundo plano (después de responder). Abre su propia sesión."""
    db = SessionLocal()
    try:
        archivo = db.query(Archivo).filter(Archivo.id == archivo_id).first()
        if not archivo or archivo.ocr_estado == "procesando":
            return
        archivo.ocr_estado = "procesando"
        db.commit()
        try:
            r = leer_texto(archivo)
        except Exception as e:  # PDF dañado, imagen ilegible, tesseract caído...
            archivo.ocr_estado = "error"
            archivo.ocr_error = (getattr(e, "detail", None) or str(e))[:300]
            db.commit()
            print(f"[ocr] {archivo.nombre_original}: {archivo.ocr_error}", flush=True)
            return
        hay_texto = bool(r["texto"].replace("\f", "").strip())
        archivo.ocr_texto = r["texto"] if hay_texto else None
        archivo.ocr_confianza = r["confianza"]
        archivo.ocr_paginas = r["paginas"]
        archivo.ocr_motor = r["motor"]
        archivo.ocr_en = datetime.now(timezone.utc)
        archivo.ocr_error = None
        archivo.ocr_estado = "listo" if hay_texto else "sin_texto"
        detalle = f"OCR: {r['paginas']} página(s)"
        if r["paginas"] < r["paginas_total"]:
            detalle += f" de {r['paginas_total']}"
        detalle += f", confianza {r['confianza']:.0f}%" if r["confianza"] is not None else ", capa de texto del PDF"
        if not hay_texto:
            detalle = f"OCR: sin texto legible ({r['paginas']} página(s))"
        db.add(LogCustodia(archivo_id=archivo.id, usuario_id=usuario_id, accion=AccionEnum.acceso, resultado=detalle))
        db.commit()
    finally:
        db.close()


def recuperar_interrumpidos() -> int:
    """Al arrancar el servidor: un OCR que quedó a medias (reinicio) se marca como error para reintentarlo."""
    db = SessionLocal()
    try:
        n = (
            db.query(Archivo)
            .filter(Archivo.ocr_estado.in_(["procesando", "pendiente"]))
            .update({"ocr_estado": "error", "ocr_error": "Se interrumpió (reinicio del servidor). Vuelve a leer el texto."},
                    synchronize_session=False)
        )
        db.commit()
        return n
    finally:
        db.close()
