"""Sprint 7 (historias 28 y 29): una página de la evidencia como imagen.

Sirve para el cotejo grafotécnico lado a lado (H28) y para el OCR (H29). Siempre se lee la
COPIA DE TRABAJO y en un archivo temporal: el original no se toca.
- Imágenes (JPG, PNG, TIFF de varias páginas, BMP, WebP...): con Pillow.
- PDF: cada página se rasteriza con `pdftoppm` (poppler-utils).
"""
import io
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from PIL import Image, ImageOps

from app.services.storage_service import abrir

EXT_IMAGEN = {"jpg", "jpeg", "png", "tif", "tiff", "bmp", "gif", "webp"}


def tipo_visual(archivo) -> Optional[str]:
    """'imagen', 'pdf' o None, según el contenido REAL detectado al subir (no la extensión)."""
    mime = (archivo.metadatos_tecnicos or {}).get("mime_detectado") or ""
    if mime == "application/pdf":
        return "pdf"
    if mime.startswith("image/"):
        return "imagen"
    if not mime:  # evidencia anterior a la historia 20: se usa la extensión
        ext = archivo.nombre_original.rsplit(".", 1)[-1].lower() if "." in archivo.nombre_original else ""
        return "pdf" if ext == "pdf" else "imagen" if ext in EXT_IMAGEN else None
    return None


def tipo_por_contenido(ruta_local: str) -> Optional[str]:
    """Sprint 7 (historia 31): 'pdf' o 'imagen' mirando los bytes (para archivos sin metadatos)."""
    with open(ruta_local, "rb") as f:
        if f.read(5) == b"%PDF-":
            return "pdf"
    try:
        with Image.open(ruta_local) as im:
            im.verify()
        return "imagen"
    except Exception:
        return None


@contextmanager
def copia_local(ruta: str):
    """La evidencia (disco o S3) copiada a un temporal que se borra al terminar."""
    with tempfile.NamedTemporaryFile(prefix="vista_", delete=False) as tmp:
        with abrir(ruta) as origen:
            shutil.copyfileobj(origen, tmp)
        nombre = tmp.name
    try:
        yield nombre
    finally:
        os.remove(nombre)


def paginas_pdf(ruta_local: str) -> int:
    salida = subprocess.run(["pdfinfo", ruta_local], capture_output=True, text=True, timeout=30).stdout
    for linea in salida.splitlines():
        if linea.startswith("Pages:"):
            return int(linea.split()[1])
    raise HTTPException(status_code=422, detail="No se pudo leer el PDF (¿está dañado o protegido con contraseña?).")


def imagen_de_pagina(ruta_local: str, tipo: str, pagina: int, dpi: int = 150) -> tuple:
    """(imagen PIL de la página, total de páginas)."""
    if tipo == "pdf":
        total = paginas_pdf(ruta_local)
        if not 1 <= pagina <= total:
            raise HTTPException(status_code=400, detail=f"El PDF tiene {total} página(s).")
        with tempfile.TemporaryDirectory(prefix="pdf_") as d:
            r = subprocess.run(
                ["pdftoppm", "-f", str(pagina), "-l", str(pagina), "-r", str(dpi), "-png", "-singlefile",
                 ruta_local, f"{d}/pagina"],
                capture_output=True, text=True, timeout=120,
            )
            if r.returncode != 0:
                raise HTTPException(status_code=422, detail="No se pudo convertir la página del PDF en imagen.")
            imagen = Image.open(f"{d}/pagina.png")
            imagen.load()
        return imagen, total
    imagen = Image.open(ruta_local)
    total = getattr(imagen, "n_frames", 1)
    if not 1 <= pagina <= total:
        raise HTTPException(status_code=400, detail=f"La imagen tiene {total} página(s).")
    imagen.seek(pagina - 1)
    imagen = ImageOps.exif_transpose(imagen)  # fotos de celular: respetar la orientación
    imagen.load()
    return imagen, total


def png_de_pagina(archivo, pagina: int = 1, max_lado: int = 2400) -> tuple:
    """(bytes PNG de la página, total de páginas) para mostrar en el navegador."""
    tipo = tipo_visual(archivo)
    if not tipo:
        raise HTTPException(status_code=415, detail="Este archivo no es una imagen ni un PDF: no se puede visualizar.")
    with copia_local(archivo.ruta_copia_trabajo) as ruta:
        imagen, total = imagen_de_pagina(ruta, tipo, pagina)
    if imagen.mode not in ("RGB", "L"):
        imagen = imagen.convert("RGB")
    imagen.thumbnail((max_lado, max_lado))  # solo achica; conserva la proporción
    salida = io.BytesIO()
    imagen.save(salida, format="PNG", optimize=True)
    return salida.getvalue(), total
