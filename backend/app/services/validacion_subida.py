"""Sprint 6 (historia 27): controles sobre los archivos que se suben como evidencia.

- Solo se aceptan extensiones de la lista (formatos usados en peritaje digital).
- El archivo se copia en trozos y se corta si supera MAX_SUBIDA_MB, sin guardarlo.
- Se rechazan ejecutables por su CONTENIDO, aunque vengan renombrados
  (usa el tipo real que detecta metadatos_service, historia 20).
"""
import os

from fastapi import HTTPException

from app.core.config import settings

EXTENSIONES_PERMITIDAS = {
    # imágenes
    "jpg", "jpeg", "png", "gif", "bmp", "tif", "tiff", "webp", "heic", "heif",
    # audio
    "mp3", "wav", "m4a", "aac", "ogg", "opus", "amr", "flac", "wma",
    # video
    "mp4", "mov", "avi", "mkv", "3gp", "webm", "wmv", "mpg", "mpeg", "m4v",
    # documentos y texto
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "rtf",
    "txt", "csv", "json", "xml", "html", "htm", "log", "eml", "msg",
    # comprimidos
    "zip", "7z", "rar", "tar", "gz",
    # formatos forenses (imágenes de disco, extracciones Cellebrite/FTK/Oxygen)
    "e01", "ex01", "l01", "aff", "aff4", "dd", "raw", "img", "bin", "iso",
    "ufd", "ufdr", "ofb", "tar.gz",
    # bases de datos de celulares
    "db", "sqlite", "sqlite3", "plist",
}

# Tipos reales que nunca se aceptan, se llamen como se llamen.
MIME_PROHIBIDOS = {
    "application/x-msdownload",        # .exe / .dll de Windows
    "application/x-executable",        # binarios ELF (Linux)
    "application/x-elf",
    "application/x-mach-binary",       # macOS
    "application/x-msi",
    "application/vnd.microsoft.portable-executable",
}

CHUNK = 1024 * 1024  # 1 MB


def validar_extension(nombre: str) -> None:
    nombre = (nombre or "").lower()
    ext = nombre.rsplit(".", 1)[-1] if "." in nombre else ""
    if nombre.endswith(".tar.gz"):
        ext = "tar.gz"
    if ext not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(
            status_code=415,
            detail=f"Tipo de archivo no permitido (.{ext or 'sin extensión'}). "
                   "Se aceptan fotos, audio, video, documentos, comprimidos y formatos forenses.",
        )


def copiar_con_limite(origen, destino) -> int:
    """Copia en trozos y corta si se pasa del máximo. Devuelve los bytes copiados."""
    limite = settings.MAX_SUBIDA_MB * 1024 * 1024
    total = 0
    while chunk := origen.read(CHUNK):
        total += len(chunk)
        if total > limite:
            raise HTTPException(
                status_code=413,
                detail=f"El archivo supera el máximo permitido de {settings.MAX_SUBIDA_MB} MB.",
            )
        destino.write(chunk)
    return total


def validar_contenido(metadatos_tecnicos: dict) -> None:
    if metadatos_tecnicos.get("mime_detectado") in MIME_PROHIBIDOS:
        raise HTTPException(
            status_code=415,
            detail="El contenido del archivo es un programa ejecutable: no se acepta como evidencia.",
        )