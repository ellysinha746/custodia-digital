import { useEffect, useState } from "react";
import api from "../api";
import { useToast } from "./Toast";
import { esVisualizable } from "../grafotecnia";

// Sprint 7 (historia 29): texto de PDFs e imágenes leído con OCR (Tesseract, en el servidor).

function nivelConfianza(c) {
  if (c == null) return { texto: "Texto digital", clase: "text-tertiary bg-tertiary/10", ayuda: "El PDF ya traía el texto: no hizo falta OCR." };
  if (c >= 85) return { texto: `Confianza alta · ${Math.round(c)}%`, clase: "text-tertiary bg-tertiary/10", ayuda: "Lectura confiable." };
  if (c >= 60) return { texto: `Confianza media · ${Math.round(c)}%`, clase: "text-amber-400 bg-amber-400/10", ayuda: "Revisa cifras y nombres contra la imagen." };
  return { texto: `Confianza baja · ${Math.round(c)}%`, clase: "text-error bg-error/10", ayuda: "Escaneo de mala calidad o texto manuscrito: compara siempre con la imagen." };
}

export default function TextoOCR({ archivo, puedeLeer, onCambio, onHistorial }) {
  const { notificar } = useToast();
  const [texto, setTexto] = useState(null); // { paginas: [...] }
  const [abierto, setAbierto] = useState(false);
  const [pagina, setPagina] = useState(0);
  const [enviando, setEnviando] = useState(false);
  const leyendo = ["pendiente", "procesando"].includes(archivo.ocr_estado);

  // Mientras se lee, se consulta cada 3 s; al terminar, se recarga el archivo.
  useEffect(() => {
    if (!leyendo) return undefined;
    const t = setInterval(async () => {
      try {
        const { data } = await api.get(`/archivos/${archivo.id}`);
        if (!["pendiente", "procesando"].includes(data.ocr_estado)) {
          clearInterval(t);
          if (data.ocr_estado === "listo") notificar(`${archivo.nombre_original}: texto leído con OCR.`, { tipo: "success" });
          onCambio?.();
          onHistorial?.();
        }
      } catch {
        clearInterval(t);
      }
    }, 3000);
    return () => clearInterval(t);
  }, [leyendo, archivo.id, archivo.nombre_original, notificar, onCambio, onHistorial]);

  if (!esVisualizable(archivo)) return null;

  const leer = async () => {
    setEnviando(true);
    try {
      await api.post(`/archivos/${archivo.id}/ocr`);
      setTexto(null);
      setAbierto(false);
      onCambio?.();
    } catch (err) {
      notificar(err.response?.data?.detail || "No se pudo iniciar la lectura.", { tipo: "error" });
    } finally {
      setEnviando(false);
    }
  };

  const alternar = async () => {
    if (!abierto && !texto) {
      try {
        const { data } = await api.get(`/archivos/${archivo.id}/ocr`);
        setTexto(data);
        setPagina(0);
      } catch {
        notificar("No se pudo cargar el texto.", { tipo: "error" });
        return;
      }
    }
    setAbierto(!abierto);
  };

  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(texto.paginas.join("\n\n"));
      notificar("Texto copiado.", { tipo: "success" });
    } catch {
      notificar("No se pudo copiar: selecciona el texto a mano.", { tipo: "error" });
    }
  };

  const botonLeer = puedeLeer && !leyendo && (
    <button
      onClick={leer}
      disabled={enviando}
      className="inline-flex items-center gap-1 font-label-ui text-label-ui text-primary hover:underline disabled:opacity-60"
    >
      <span className="material-symbols-outlined text-base">document_scanner</span>
      {archivo.ocr_estado ? "Volver a leer" : "Leer texto (OCR)"}
    </button>
  );

  const nivel = nivelConfianza(archivo.ocr_confianza);

  return (
    <div>
      <div className="flex items-center justify-between mb-1 gap-space-sm flex-wrap">
        <span className="font-label-ui text-label-ui text-outline uppercase tracking-wider">Texto del documento (OCR)</span>
        <div className="flex items-center gap-space-md">
          {archivo.ocr_estado === "listo" && (
            <button onClick={alternar} className="inline-flex items-center gap-1 font-label-ui text-label-ui text-primary hover:underline">
              <span className="material-symbols-outlined text-base">{abierto ? "visibility_off" : "article"}</span>
              {abierto ? "Ocultar texto" : "Ver texto"}
            </button>
          )}
          {botonLeer}
        </div>
      </div>

      {!archivo.ocr_estado && (
        <p className="font-body-sm text-body-sm text-outline">Este documento se subió antes de la lectura automática de texto.</p>
      )}
      {leyendo && (
        <p className="font-body-sm text-body-sm text-on-surface-variant flex items-center gap-2">
          <span className="material-symbols-outlined text-lg animate-spin">progress_activity</span>
          Leyendo el texto… En PDFs escaneados de muchas páginas puede tardar un par de minutos.
        </p>
      )}
      {archivo.ocr_estado === "error" && (
        <p className="font-body-sm text-body-sm text-error">No se pudo leer el texto: {archivo.ocr_error}</p>
      )}
      {archivo.ocr_estado === "sin_texto" && (
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          No se encontró texto impreso legible. El OCR no lee firmas y es poco fiable con letra manuscrita.
        </p>
      )}
      {archivo.ocr_estado === "listo" && (
        <div className="flex items-center gap-2 flex-wrap font-body-sm text-body-sm">
          <span title={nivel.ayuda} className={`px-2 py-0.5 rounded font-label-ui text-label-ui ${nivel.clase}`}>{nivel.texto}</span>
          <span className="text-on-surface-variant">{archivo.ocr_paginas} página(s)</span>
          <span className="text-outline font-label-code-sm text-label-code-sm">· {archivo.ocr_motor}</span>
        </div>
      )}

      {abierto && texto && (
        <div className="mt-space-sm bg-surface-container-high rounded-lg p-space-sm flex flex-col gap-space-sm">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            {texto.paginas.length > 1 ? (
              <div className="flex gap-1 flex-wrap">
                {texto.paginas.map((_, i) => (
                  <button
                    key={i}
                    onClick={() => setPagina(i)}
                    className={`px-2 py-0.5 rounded font-label-code-sm text-label-code-sm ${
                      i === pagina ? "bg-primary text-on-primary" : "bg-surface-container text-on-surface-variant hover:bg-surface-container-low"
                    }`}
                  >
                    Pág. {i + 1}
                  </button>
                ))}
              </div>
            ) : <span />}
            <button onClick={copiar} className="inline-flex items-center gap-1 font-label-ui text-label-ui text-primary hover:underline">
              <span className="material-symbols-outlined text-base">content_copy</span>Copiar todo
            </button>
          </div>
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words font-label-code-sm text-label-code-sm text-on-surface">
            {texto.paginas[pagina]?.trim() || "(página sin texto)"}
          </pre>
          <p className="font-body-sm text-body-sm text-outline">
            Texto obtenido automáticamente: puede tener errores. Para el informe, contrástalo con el documento.
          </p>
        </div>
      )}
    </div>
  );
}
