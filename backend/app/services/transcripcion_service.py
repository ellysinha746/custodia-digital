"""Sprint 8 (historia 40): transcripción de audio y video con Whisper, dentro del servidor.

Se usa faster-whisper (Whisper de OpenAI optimizado para CPU). El modelo se descarga UNA vez
desde Hugging Face y queda guardado en WHISPER_DIR; desde ahí todo corre en el laboratorio:
el audio de la evidencia nunca sale del servidor.

Se transcribe la COPIA DE TRABAJO. El texto se guarda con marcas de tiempo por frase y con su
SHA-256: si alguien edita la transcripción en la base, la verificación lo muestra.
"""
import hashlib
import threading
from datetime import datetime, timezone
from typing import Dict, List
from uuid import UUID

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.archivo import Archivo
from app.models.log_custodia import AccionEnum, LogCustodia
from app.services import vista_service

EXT_AUDIO_VIDEO = {
    "mp3", "wav", "m4a", "aac", "ogg", "oga", "opus", "flac", "amr", "wma", "3gp",
    "mp4", "mov", "avi", "mkv", "webm", "m4v", "mpeg", "mpg", "wmv",
}
_modelo = None
_candado = threading.Lock()  # un audio a la vez: el modelo usa mucha CPU y memoria


def es_audio_o_video(archivo: Archivo) -> bool:
    tec = archivo.metadatos_tecnicos or {}
    if tec.get("categoria") in ("audio", "video"):
        return True
    mime = tec.get("mime_detectado") or ""
    if mime:
        return mime.startswith("audio/") or mime.startswith("video/")
    ext = archivo.nombre_original.rsplit(".", 1)[-1].lower() if "." in archivo.nombre_original else ""
    return ext in EXT_AUDIO_VIDEO


def duracion_segundos(archivo: Archivo):
    """Duración que midió ffprobe al subir (historia 20, campo "Duración" = HH:MM:SS.mmm)."""
    for c in (archivo.metadatos_tecnicos or {}).get("campos") or []:
        if c.get("campo") == "Duración":
            try:
                h, m, s = str(c["valor"]).split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
            except (ValueError, KeyError):
                return None
    return None


def huella(texto: str) -> str:
    return hashlib.sha256((texto or "").encode("utf-8")).hexdigest()


def _cargar_modelo():
    global _modelo
    if _modelo is None:
        from faster_whisper import WhisperModel  # import tardío: la API arranca rápido igual
        _modelo = WhisperModel(settings.WHISPER_MODELO, device="cpu", compute_type="int8", download_root=settings.WHISPER_DIR)
    return _modelo


def _motor() -> str:
    try:
        from importlib.metadata import version
        v = version("faster-whisper")
    except Exception:
        v = "?"
    return f"faster-whisper {v} ({settings.WHISPER_MODELO}, int8, CPU)"


def transcribir(ruta_local: str) -> Dict:
    """Transcribe un archivo de audio o video del disco. Devuelve texto, segmentos e idioma."""
    with _candado:
        modelo = _cargar_modelo()
        segmentos_it, info = modelo.transcribe(
            ruta_local,
            language=settings.WHISPER_IDIOMA or None,
            vad_filter=True,          # salta silencios y ruido: menos "alucinaciones"
            beam_size=5,
            condition_on_previous_text=False,
        )
        segmentos: List[Dict] = [
            {"inicio": round(s.start, 2), "fin": round(s.end, 2), "texto": s.text.strip()}
            for s in segmentos_it
            if s.text.strip()
        ]
    return {
        "texto": "\n".join(s["texto"] for s in segmentos),
        "segmentos": segmentos,
        "idioma": info.language,
        "duracion": round(float(info.duration), 2),
        "motor": _motor(),
    }


def preparar(archivo: Archivo) -> bool:
    """Marca el archivo como pendiente de transcripción si es audio o video (no hace commit)."""
    if not es_audio_o_video(archivo):
        return False
    archivo.transcripcion_estado = "pendiente"
    archivo.transcripcion_error = None
    return True


def procesar(archivo_id: UUID, usuario_id: UUID) -> None:
    """Corre en segundo plano (después de responder). Abre su propia sesión."""
    db = SessionLocal()
    try:
        archivo = db.query(Archivo).filter(Archivo.id == archivo_id).first()
        if not archivo or archivo.transcripcion_estado == "procesando":
            return
        archivo.transcripcion_estado = "procesando"
        db.commit()
        try:
            with vista_service.copia_local(archivo.ruta_copia_trabajo) as ruta:
                r = transcribir(ruta)
        except Exception as e:  # formato dañado, sin internet para bajar el modelo la primera vez...
            archivo.transcripcion_estado = "error"
            archivo.transcripcion_error = str(e)[:300]
            db.commit()
            print(f"[whisper] {archivo.nombre_original}: {archivo.transcripcion_error}", flush=True)
            return
        hay_voz = bool(r["texto"].strip())
        archivo.transcripcion_texto = r["texto"] if hay_voz else None
        archivo.transcripcion_segmentos = r["segmentos"]
        archivo.transcripcion_idioma = r["idioma"]
        archivo.transcripcion_duracion = r["duracion"]
        archivo.transcripcion_motor = r["motor"]
        archivo.transcripcion_sha256 = huella(r["texto"]) if hay_voz else None
        archivo.transcripcion_en = datetime.now(timezone.utc)
        archivo.transcripcion_error = None
        archivo.transcripcion_estado = "listo" if hay_voz else "sin_voz"
        minutos = r["duracion"] / 60
        detalle = (
            f"transcripción Whisper: {len(r['segmentos'])} frase(s), {minutos:.1f} min, idioma {r['idioma']}"
            if hay_voz else f"transcripción Whisper: no se detectó voz ({minutos:.1f} min)"
        )
        db.add(LogCustodia(archivo_id=archivo.id, usuario_id=usuario_id, accion=AccionEnum.acceso, resultado=detalle))
        db.commit()
    finally:
        db.close()


def recuperar_interrumpidos() -> int:
    """Al arrancar: una transcripción cortada por un reinicio queda como error para reintentarla."""
    db = SessionLocal()
    try:
        n = (
            db.query(Archivo)
            .filter(Archivo.transcripcion_estado.in_(["procesando", "pendiente"]))
            .update({"transcripcion_estado": "error",
                     "transcripcion_error": "Se interrumpió (reinicio del servidor). Vuelve a transcribir."},
                    synchronize_session=False)
        )
        db.commit()
        return n
    finally:
        db.close()


def a_texto_con_tiempos(archivo: Archivo) -> str:
    """Transcripción para descargar: cabecera con la huella de la evidencia y frases con su minuto."""
    def mmss(s):
        s = int(s)
        return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"
    lineas = [
        "CustodiaDigital - transcripción automática (apoyo al perito, revisar contra el audio)",
        f"archivo: {archivo.nombre_original}",
        f"SHA-256 de la evidencia (original): {archivo.hash_original or '-'}",
        f"motor: {archivo.transcripcion_motor} · idioma: {archivo.transcripcion_idioma}",
        f"transcrito: {archivo.transcripcion_en.isoformat() if archivo.transcripcion_en else '-'}",
        f"SHA-256 del texto: {archivo.transcripcion_sha256 or '-'}",
        "",
    ]
    for s in archivo.transcripcion_segmentos or []:
        lineas.append(f"[{mmss(s['inicio'])} - {mmss(s['fin'])}] {s['texto']}")
    return "\n".join(lineas) + "\n"
