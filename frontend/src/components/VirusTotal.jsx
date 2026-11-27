import { useState } from "react";
import api from "../api";
import { useToast } from "./Toast";

const MENSAJE = {
  limpio: { t: "Sin detecciones en VirusTotal", c: "text-tertiary" },
  malicioso: { t: "Detectado como malicioso", c: "text-error" },
  desconocido: { t: "VirusTotal no conoce este archivo (es normal en evidencia propia)", c: "text-on-surface-variant" },
  limite: { t: "Límite de consultas alcanzado, reintenta en un minuto", c: "text-amber-400" },
  no_configurado: { t: "VirusTotal no está configurado en el servidor", c: "text-amber-400" },
  error: { t: "No se pudo consultar VirusTotal", c: "text-error" },
};

export default function VirusTotal({ archivo, onHistorial }) {
  const { notificar } = useToast();
  const [cargando, setCargando] = useState(false);
  const [res, setRes] = useState(null);

  const consultar = async () => {
    setCargando(true);
    try {
      const { data } = await api.post(`/archivos/${archivo.id}/virustotal`);
      setRes(data);
      if (onHistorial) onHistorial();
    } catch {
      notificar("No se pudo consultar VirusTotal.", { tipo: "error" });
    } finally {
      setCargando(false);
    }
  };

  const m = res && (MENSAJE[res.estado] || MENSAJE.error);
  return (
    <div className="mt-3 flex flex-wrap items-center gap-3">
      <button
        onClick={consultar}
        disabled={cargando || !archivo.hash_original}
        className="px-3 py-1.5 rounded-md border border-outline-variant/40 font-label-ui text-label-ui text-on-surface hover:border-primary/50 disabled:opacity-50"
      >
        {cargando ? "Consultando…" : "Consultar en VirusTotal"}
      </button>
      {m && (
        <span className={`font-body-sm text-body-sm ${m.c}`}>
          {m.t}
          {res.total > 0 && ` (${res.malicioso + res.sospechoso}/${res.total} motores)`}
          {res.enlace && (
            <a href={res.enlace} target="_blank" rel="noreferrer" className="ml-2 underline text-primary">
              Ver informe
            </a>
          )}
        </span>
      )}
    </div>
  );
}