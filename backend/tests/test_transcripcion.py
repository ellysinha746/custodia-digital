"""Sprint 8 (historia 40): transcripción con Whisper.

El modelo de Whisper se SIMULA (no se descarga en las pruebas). Sí se prueba de verdad la
lectura del audio con PyAV, que es lo que usa faster-whisper por dentro."""
import math
import struct
import wave
from collections import namedtuple
from datetime import datetime, timezone
from types import SimpleNamespace

from faster_whisper import decode_audio

from app.services import transcripcion_service as ts

Segmento = namedtuple("Segmento", "start end text")


class ModeloFalso:
    def transcribe(self, ruta, **kwargs):
        assert kwargs["vad_filter"] is True  # se saltan los silencios
        segs = [Segmento(0.0, 2.5, " Buenas tardes, habla el comprador."), Segmento(2.5, 3.0, "  "),
                Segmento(3.0, 6.2, " Le deposito los 15 mil soles mañana.")]
        return iter(segs), SimpleNamespace(language="es", duration=6.2)


def _wav(ruta, segundos=1.0, hz=440):
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * hz * i / 16000)))
                               for i in range(int(16000 * segundos))))


def test_pyav_lee_el_audio(tmp_path):
    ruta = tmp_path / "llamada.wav"
    _wav(ruta, segundos=1.0)
    audio = decode_audio(str(ruta), sampling_rate=16000)
    assert abs(len(audio) - 16000) < 200


def test_transcribir_arma_texto_y_frases(tmp_path, monkeypatch):
    monkeypatch.setattr(ts, "_cargar_modelo", lambda: ModeloFalso())
    ruta = tmp_path / "llamada.wav"
    _wav(ruta)
    r = ts.transcribir(str(ruta))
    assert r["idioma"] == "es" and r["duracion"] == 6.2
    assert len(r["segmentos"]) == 2, "las frases vacías se descartan"
    assert r["texto"] == "Buenas tardes, habla el comprador.\nLe deposito los 15 mil soles mañana."


def _archivo(**extra):
    base = dict(nombre_original="llamada.mp3", metadatos_tecnicos={}, hash_original="ab" * 32,
                transcripcion_motor="faster-whisper (base)", transcripcion_idioma="es",
                transcripcion_en=datetime(2026, 11, 24, tzinfo=timezone.utc), transcripcion_sha256="x",
                transcripcion_segmentos=[{"inicio": 65.0, "fin": 70.4, "texto": "Hola"}])
    base.update(extra)
    return SimpleNamespace(**base)


def test_detecta_audio_y_video_por_contenido():
    assert ts.es_audio_o_video(_archivo(metadatos_tecnicos={"categoria": "audio"}))
    assert ts.es_audio_o_video(_archivo(nombre_original="x.bin", metadatos_tecnicos={"mime_detectado": "video/mp4"}))
    assert not ts.es_audio_o_video(_archivo(nombre_original="foto.mp3", metadatos_tecnicos={"mime_detectado": "image/png"}))


def test_duracion_desde_ffprobe():
    a = _archivo(metadatos_tecnicos={"campos": [{"campo": "Duración", "valor": "01:02:03.500"}]})
    assert ts.duracion_segundos(a) == 3723.5
    assert ts.duracion_segundos(_archivo()) is None


def test_texto_descargable_con_minutos():
    texto = ts.a_texto_con_tiempos(_archivo())
    assert "[00:01:05 - 00:01:10] Hola" in texto
    assert "SHA-256 de la evidencia (original): " + "ab" * 32 in texto


def test_huella_detecta_texto_editado():
    original = "Le deposito los 15 mil soles mañana."
    assert ts.huella(original) != ts.huella(original.replace("15", "50"))
