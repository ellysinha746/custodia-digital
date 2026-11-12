"""Sprint 6 (historia 20): metadatos técnicos automáticos de la evidencia.

Al subir un archivo se extrae, sin intervención del perito:
  - el TIPO REAL del archivo por su contenido (firma binaria), y si coincide con la
    extensión del nombre (un .jpg que en realidad es un .exe se marca);
  - fotos: EXIF (cámara, fecha de captura, software de edición, GPS);
  - audio y video: ffprobe (duración, códec, resolución, fecha de creación, equipo);
  - PDF: autor, programa que lo generó y fechas.

Nunca lanza excepciones hacia afuera: si algo no se puede leer, lo anota en "avisos"
y la subida continúa.
"""
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, Optional

EXTENSIONES_EQUIVALENTES = {
    "jpg": {"jpg", "jpeg", "jpe", "jfif"},
    "tif": {"tif", "tiff"},
    "mp4": {"mp4", "m4v", "m4a", "mov", "3gp", "3g2"},
    "mov": {"mov", "mp4", "m4v", "qt"},
    "m4a": {"m4a", "mp4", "aac"},
    "ogg": {"ogg", "oga", "opus", "ogv"},
    "mkv": {"mkv", "webm", "mka"},
    "webm": {"webm", "mkv"},
    "zip": {"zip", "docx", "xlsx", "pptx", "odt", "ods", "apk", "jar", "ufd", "ufdr"},
    "mpg": {"mpg", "mpeg"},
    "3gp": {"3gp", "3gpp", "mp4", "amr"},
}


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _grados(valor, ref) -> Optional[float]:
    """Convierte coordenadas EXIF (grados, minutos, segundos) a decimal."""
    try:
        g, m, s = (float(x) for x in valor)
        dec = g + m / 60 + s / 3600
        return round(-dec if ref in ("S", "W") else dec, 6)
    except Exception:
        return None


def _fecha_legible(v: str) -> str:
    """Normaliza fechas EXIF (2026:10:12 21:14:03), PDF (D:20261012211403-05'00')
    e ISO (2026-10-12T21:14:03Z) a 12/10/2026 21:14:03."""
    import re

    m = re.match(r"^D?:?(\d{4})[:\-]?(\d{2})[:\-]?(\d{2})[ T]?(\d{2}):?(\d{2}):?(\d{2})", v.strip())
    if not m:
        return v
    a, me, d, h, mi, se = m.groups()
    sufijo = " UTC" if v.strip().endswith("Z") else ""
    return f"{d}/{me}/{a} {h}:{mi}:{se}{sufijo}"


def _texto(v) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, bytes):
        v = v.decode("utf-8", "ignore")
    v = str(v).strip().strip("\x00")
    return v or None


# ---------------------------------------------------------------- tipo real

def _tipo_real(ruta: str, nombre: str) -> Dict[str, Any]:
    import filetype

    ext_declarada = os.path.splitext(nombre or "")[1].lower().lstrip(".")
    tipo = filetype.guess(ruta)
    if tipo is None:
        # Sin firma binaria conocida (texto plano, CSV, logs...): no se puede contrastar.
        return {"mime_detectado": None, "extension_real": None, "extension_declarada": ext_declarada or None,
                "extension_coincide": None}
    validas = EXTENSIONES_EQUIVALENTES.get(tipo.extension, {tipo.extension})
    return {
        "mime_detectado": tipo.mime,
        "extension_real": tipo.extension,
        "extension_declarada": ext_declarada or None,
        "extension_coincide": ext_declarada in validas if ext_declarada else False,
    }


def _categoria(mime: Optional[str], nombre: str) -> str:
    if mime:
        if mime.startswith("image/"):
            return "imagen"
        if mime.startswith("video/"):
            return "video"
        if mime.startswith("audio/"):
            return "audio"
        if mime == "application/pdf":
            return "documento"
    ext = os.path.splitext(nombre or "")[1].lower()
    if ext in (".wav", ".mp3", ".m4a", ".amr", ".ogg", ".opus", ".aac", ".flac"):
        return "audio"
    if ext in (".mp4", ".mov", ".avi", ".mkv", ".3gp", ".webm", ".mpg"):
        return "video"
    return "otro"


# ---------------------------------------------------------------- imágenes

def _exif(ruta: str) -> Dict[str, Any]:
    from PIL import Image, ExifTags

    with Image.open(ruta) as img:
        datos: Dict[str, Any] = {
            "Formato": img.format,
            "Resolución": f"{img.width} × {img.height} px",
            "Modo de color": img.mode,
        }
        exif = img.getexif()
        if not exif:
            return {"campos": datos, "exif_presente": False}

        etiquetas = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
        # Los datos de la toma (fecha original, exposición) están en el sub-IFD Exif.
        try:
            sub = exif.get_ifd(ExifTags.IFD.Exif)
            etiquetas.update({ExifTags.TAGS.get(k, k): v for k, v in sub.items()})
        except Exception:
            pass

        for etiqueta, clave in (
            ("Fabricante", "Make"),
            ("Modelo", "Model"),
            ("Fecha de captura", "DateTimeOriginal"),
            ("Fecha de modificación", "DateTime"),
            ("Software", "Software"),
            ("Autor", "Artist"),
        ):
            v = _texto(etiquetas.get(clave))
            if v:
                datos[etiqueta] = v

        gps = None
        try:
            g = exif.get_ifd(ExifTags.IFD.GPSInfo)
            if g:
                lat = _grados(g.get(2), _texto(g.get(1)))
                lon = _grados(g.get(4), _texto(g.get(3)))
                if lat is not None and lon is not None:
                    gps = {"lat": lat, "lon": lon}
        except Exception:
            pass

        return {"campos": datos, "exif_presente": True, "gps": gps}


# ---------------------------------------------------------------- audio / video

def _ffprobe(ruta: str) -> Dict[str, Any]:
    if not shutil.which("ffprobe"):
        return {"aviso": "ffprobe no está instalado en el servidor."}
    salida = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", ruta],
        capture_output=True, text=True, timeout=60,
    )
    if salida.returncode != 0:
        return {"aviso": "ffprobe no pudo leer el archivo (¿dañado o formato no soportado?)."}
    info = json.loads(salida.stdout or "{}")
    fmt = info.get("format", {})
    tags = {k.lower(): v for k, v in (fmt.get("tags") or {}).items()}
    datos: Dict[str, Any] = {}

    if fmt.get("format_long_name"):
        datos["Contenedor"] = fmt["format_long_name"]
    if fmt.get("duration"):
        seg = float(fmt["duration"])
        datos["Duración"] = f"{int(seg // 3600):02d}:{int(seg % 3600 // 60):02d}:{seg % 60:06.3f}"
    if fmt.get("bit_rate"):
        datos["Tasa de bits"] = f"{int(fmt['bit_rate']) // 1000} kb/s"
    for etiqueta, clave in (
        ("Fecha de creación", "creation_time"),
        ("Fabricante", "com.apple.quicktime.make"),
        ("Modelo", "com.apple.quicktime.model"),
        ("Software / codificador", "encoder"),
        ("Ubicación", "location"),
    ):
        if tags.get(clave):
            datos[etiqueta] = tags[clave]

    for st in info.get("streams", []):
        if st.get("codec_type") == "video" and "Códec de video" not in datos:
            datos["Códec de video"] = st.get("codec_long_name") or st.get("codec_name")
            if st.get("width"):
                datos["Resolución"] = f"{st['width']} × {st['height']} px"
            fr = st.get("avg_frame_rate") or ""
            if "/" in fr and not fr.endswith("/0"):
                n, d = fr.split("/")
                if float(d):
                    datos["Cuadros por segundo"] = round(float(n) / float(d), 2)
        elif st.get("codec_type") == "audio" and "Códec de audio" not in datos:
            datos["Códec de audio"] = st.get("codec_long_name") or st.get("codec_name")
            if st.get("sample_rate"):
                datos["Frecuencia de muestreo"] = f"{st['sample_rate']} Hz"
            if st.get("channels"):
                datos["Canales"] = st["channels"]
    return {"campos": datos}


# ---------------------------------------------------------------- PDF

def _pdf(ruta: str) -> Dict[str, Any]:
    from pypdf import PdfReader

    lector = PdfReader(ruta)
    meta = lector.metadata or {}
    datos: Dict[str, Any] = {"Páginas": len(lector.pages)}
    for etiqueta, clave in (
        ("Título", "/Title"),
        ("Autor", "/Author"),
        ("Creado con", "/Creator"),
        ("Generado por", "/Producer"),
        ("Fecha de creación", "/CreationDate"),
        ("Fecha de modificación", "/ModDate"),
    ):
        v = _texto(meta.get(clave))
        if v:
            datos[etiqueta] = v
    datos["Cifrado"] = "Sí" if lector.is_encrypted else "No"
    return {"campos": datos}


# ---------------------------------------------------------------- principal

def extraer_metadatos(ruta_local: str, nombre: str) -> Dict[str, Any]:
    """Extrae los metadatos técnicos de un archivo que está en disco local."""
    resultado: Dict[str, Any] = {
        "extraido_en": _ahora(),
        "tamano_bytes": os.path.getsize(ruta_local),
        "campos": {},
        "avisos": [],
        "herramientas": [],
    }
    try:
        resultado.update(_tipo_real(ruta_local, nombre))
        resultado["herramientas"].append("firma binaria (filetype)")
    except Exception as e:
        resultado["avisos"].append(f"No se pudo detectar el tipo real: {e}")

    categoria = _categoria(resultado.get("mime_detectado"), nombre)
    resultado["categoria"] = categoria

    try:
        if categoria == "imagen":
            parte = _exif(ruta_local)
            resultado["herramientas"].append("EXIF (Pillow)")
            if not parte.get("exif_presente"):
                resultado["avisos"].append("La imagen no tiene EXIF (puede haber sido editada, recortada o enviada por mensajería).")
        elif categoria in ("audio", "video"):
            parte = _ffprobe(ruta_local)
            resultado["herramientas"].append("ffprobe")
        elif categoria == "documento":
            parte = _pdf(ruta_local)
            resultado["herramientas"].append("pypdf")
        else:
            parte = {}
        if parte.get("aviso"):
            resultado["avisos"].append(parte.pop("aviso"))
        resultado["campos"].update(parte.get("campos", {}))
        if parte.get("gps"):
            resultado["gps"] = parte["gps"]
    except Exception as e:
        resultado["avisos"].append(f"No se pudieron leer los metadatos: {e}")

    # Fechas legibles y lista ordenada (JSONB no conserva el orden de las claves).
    resultado["campos"] = [
        {"campo": k, "valor": _fecha_legible(v) if k.startswith("Fecha") and isinstance(v, str) else v}
        for k, v in resultado["campos"].items()
    ]

    if resultado.get("extension_coincide") is False:
        resultado["avisos"].insert(
            0,
            f"La extensión .{resultado.get('extension_declarada') or '(ninguna)'} no coincide con el contenido real "
            f"({resultado.get('mime_detectado')}).",
        )
    return resultado