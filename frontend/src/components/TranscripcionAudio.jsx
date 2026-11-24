import { useEffect, useState } from "react";
import api from "../api";
import { useToast } from "./Toast";

// Sprint 8 (historia 40): transcripción de audio y video con Whisper, dentro del servidor.

const EXT_AUDIO_VIDEO = ["mp3", "wav", "m4a", "aac", "ogg", "oga", "opus", "flac", "amr", "wma", "3gp", "mp4", "mov", "avi", "mkv", "webm", "m4v", "mpeg", "mpg", "wmv"];

function esAudioVideo(archivo) {
  const tec = archivo.metadatos_tecnicos || {};
  if (["audio", "video"].includes(tec.categoria)) return true;
  const mime = tec.mime_detectado || "";
  if (mime) return mime.startsWith("audio/") || mime.startsWith("video/");
  const ext = archivo.nombre_original.includes(".") ? archivo.nombre_original.split(".").pop().toLowerCase() : "";
  return EXT_AUDIO_VIDEO.includes(ext);
}

function minuto(seg) {
  const s = Math.floor(seg);
  const h = Math.floor(s / 3600);
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

export default function TranscripcionAudio({ archivo, puedeTranscribir, onCambio, onHistorial }) {
  const { notificar } = useToast();
  const [datos, setDatos] = useState(null);
  const [abierto, setAbierto] = useState(false);
  const [filtro, setFiltro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const trabajando = ["pendiente", "procesando"].includes(archivo.transcripcion_estado);

  // Mientras transcribe, se consulta cada 5 s; al terminar, se recarga el archivo.
  useEffect(() => {
    if (!trabajando) return undefined;
    const t = setInterval(async () => {
      try {
        const { data } = await api.get(`/archivos/${archivo.id}`);
        if (!["pendiente", "procesando"].includes(data.transcripcion_estado)) {
          clearInterval(t);
          if (data.transcripcion_estado === "listo") notificar(`${archivo.nombre_original}: transcripción lista.`, { tipo: "success" });
          onCambio?.();
          onHistorial?.();
        }
      } catch {
        clearInterval(t);
      }
    }, 5000);
    return () => clearInterval(t);
  }, [trabajando, archivo.id, archivo.nombre_original, notificar, onCambio, onHistorial]);

  if (!esAudioVideo(archivo)) return null;

  const transcribir = async () => {
    setEnviando(true);
    try {
      await api.post(`/archivos/${archivo.id}/transcripcion`);
      setDatos(null);
      setAbierto(false);
      onCambio?.();
    } catch (err) {
      notificar(err.response?.data?.detail || "No se pudo iniciar la transcripción.", { tipo: "error" });
    } finally {
      setEnviando(false);
    }
  };

  const alternar = async () => {
    if (!abierto && !datos) {
      try {
        const { data } = await api.get(`/archivos/${archivo.id}/transcripcion`);
        setDatos(data);
      } catch {
        notificar("No se pudo cargar la transcripción.", { tipo: "error" });
        return;
      }
    }
    setAbierto(!abierto);
  };

  const descargar = async () => {
    try {
      const { data } = await api.get(`/archivos/${archivo.id}/transcripcion.txt`, { responseType: "blob" });
      const enlace = URL.createObjectURL(data);
      const a = document.createElement("a");
      a.href = enlace;
      a.download = `${archivo.nombre_original.replace(/\.[^.]+$/, "")}_transcripcion.txt`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(enlace);
      onHistorial?.();
    } catch {
      notificar("No se pudo descargar la transcripción.", { tipo: "error" });
    }
  };

  const segmentos = (datos?.segmentos || []).filter((s) => !filtro || s.texto.toLowerCase().includes(filtro.toLowerCase()));

  return (
    <div>
      <div className="flex items-center justify-between mb-1 gap-space-sm flex-wrap">
        <span className="font-label-ui text-label-ui text-outline uppercase tracking-wider">Transcripción del audio (Whisper)</span>
        <div className="flex items-center gap-space-md">
          {archivo.transcripcion_estado === "listo" && (
            <>
              <button onClick={alternar} className="inline-flex items-center gap-1 font-label-ui text-label-ui text-primary hover:underline">
                <span className="material-symbols-outlined text-base">{abierto ? "visibility_off" : "subtitles"}</span>
                {abierto ? "Ocultar" : "Ver transcripción"}
              </button>
              <button onClick={descargar} className="inline-flex items-center gap-1 font-label-ui text-label-ui text-primary hover:underline">
                <span className="material-symbols-outlined text-base">download</span>.txt
              </button>
            </>
          )}
          {puedeTranscribir && !trabajando && (
            <button
              onClick={transcribir}
              disabled={enviando}
              className="inline-flex items-center gap-1 font-label-ui text-label-ui text-primary hover:underline disabled:opacity-60"
            >
              <span className="material-symbols-outlined text-base">record_voice_over</span>
              {archivo.transcripcion_estado ? "Volver a transcribir" : "Transcribir"}
            </button>
          )}
        </div>
      </div>

      {!archivo.transcripcion_estado && (
        <p className="font-body-sm text-body-sm text-outline">Todavía no se transcribió este audio.</p>
      )}
      {trabajando && (
        <p className="font-body-sm text-body-sm text-on-surface-variant flex items-center gap-2">
          <span className="material-symbols-outlined text-lg animate-spin">progress_activity</span>
          Transcribiendo… Tarda aproximadamente lo mismo que dura el audio (la primera vez, más: se descarga el modelo).
        </p>
      )}
      {archivo.transcripcion_estado === "error" && (
        <p className="font-body-sm text-body-sm text-error">No se pudo transcribir: {archivo.transcripcion_error}</p>
      )}
      {archivo.transcripcion_estado === "sin_voz" && (
        <p className="font-body-sm text-body-sm text-on-surface-variant">No se detectó voz en este archivo.</p>
      )}
      {archivo.transcripcion_estado === "listo" && (
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          {minuto(archivo.transcripcion_duracion || 0)} de audio
          <span className="text-outline font-label-code-sm text-label-code-sm"> · {archivo.transcripcion_motor}</span>
        </p>
      )}

      {abierto && datos && (
        <div className="mt-space-sm bg-surface-container-high rounded-lg p-space-sm flex flex-col gap-space-sm">
          <div className="flex items-center gap-space-sm flex-wrap">
            <input
              value={filtro}
              onChange={(e) => setFiltro(e.target.value)}
              placeholder="Buscar en lo que se dijo…"
              className="flex-1 min-w-48 bg-surface-container rounded px-2 py-1 font-body-sm text-body-sm text-on-surface placeholder:text-outline"
            />
            <span
              className={`px-2 py-0.5 rounded font-label-ui text-label-ui ${datos.integra ? "text-tertiary bg-tertiary/10" : "text-error bg-error/10"}`}
              title={`SHA-256 del texto: ${datos.sha256}`}
            >
              {datos.integra ? "Texto íntegro" : "El texto guardado fue modificado"}
            </span>
          </div>
          <div className="max-h-80 overflow-auto flex flex-col gap-1">
            {segmentos.map((s, i) => (
              <p key={i} className="font-body-sm text-body-sm text-on-surface">
                <span className="font-label-code-sm text-label-code-sm text-primary mr-2">[{minuto(s.inicio)}]</span>
                {s.texto}
              </p>
            ))}
            {segmentos.length === 0 && <p className="font-body-sm text-body-sm text-outline">No hay frases con ese texto.</p>}
          </div>
          <p className="font-body-sm text-body-sm text-outline">
            Transcripción automática ({datos.idioma}): puede tener errores en nombres y cifras. Para el informe, contrástala con el audio.
          </p>
        </div>
      )}
    </div>
  );
}
