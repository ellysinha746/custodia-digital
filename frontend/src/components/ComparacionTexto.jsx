import { useState } from "react";
import api from "../api";
import { useToast } from "./Toast";

// Sprint 7 (historia 31): compara el texto (OCR) de este documento con otra versión:
// otro documento del caso o una versión observada subida por el perito de parte.
// Resalta las palabras y, sobre todo, las CIFRAS que cambiaron.

const MAX_IGUALES = 14; // palabras iguales que se muestran alrededor de cada cambio

function Segmento({ s, expandido, onExpandir }) {
  if (s.tipo === "igual") {
    const palabras = s.texto.split(" ");
    if (expandido || palabras.length <= MAX_IGUALES * 2) return <span className="text-on-surface-variant">{s.texto} </span>;
    return (
      <span className="text-on-surface-variant">
        {palabras.slice(0, MAX_IGUALES).join(" ")}{" "}
        <button onClick={onExpandir} className="px-1.5 rounded bg-surface-container text-outline font-label-code-sm text-label-code-sm hover:text-primary">
          … {palabras.length - MAX_IGUALES * 2} palabras iguales …
        </button>{" "}
        {palabras.slice(-MAX_IGUALES).join(" ")}{" "}
      </span>
    );
  }
  return (
    <span>
      {s.antes && <del className="bg-error/20 text-error px-0.5 rounded decoration-2">{s.antes}</del>}
      {s.antes && s.despues && " "}
      {s.despues && <ins className="bg-tertiary/20 text-tertiary px-0.5 rounded no-underline font-semibold">{s.despues}</ins>}{" "}
    </span>
  );
}

export default function ComparacionTexto({ archivo, archivos }) {
  const { notificar } = useToast();
  const [abierto, setAbierto] = useState(false);
  const [versiones, setVersiones] = useState([]);
  const [contra, setContra] = useState("");
  const [comparando, setComparando] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [expandidos, setExpandidos] = useState({});

  if (archivo.ocr_estado !== "listo") return null;
  const otros = archivos.filter((a) => a.id !== archivo.id && a.ocr_estado === "listo");

  const abrir = async () => {
    setAbierto(!abierto);
    if (!abierto) {
      try {
        const { data } = await api.get(`/archivos/${archivo.id}/observadas`);
        setVersiones(data);
      } catch {
        setVersiones([]);
      }
    }
  };

  const comparar = async () => {
    setComparando(true);
    setResultado(null);
    setExpandidos({});
    const [tipo, id] = contra.split(":");
    try {
      const { data } = await api.post(`/archivos/${archivo.id}/comparar-texto`, tipo === "v" ? { contra_version_id: id } : { contra_archivo_id: id });
      setResultado(data);
    } catch (err) {
      notificar(err.response?.data?.detail || "No se pudo comparar el texto.", { tipo: "error" });
    } finally {
      setComparando(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-1 gap-space-sm flex-wrap">
        <span className="font-label-ui text-label-ui text-outline uppercase tracking-wider">Comparar texto con otra versión</span>
        <button onClick={abrir} className="inline-flex items-center gap-1 font-label-ui text-label-ui text-primary hover:underline">
          <span className="material-symbols-outlined text-base">difference</span>
          {abierto ? "Cerrar" : "Comparar"}
        </button>
      </div>

      {abierto && (
        <div className="bg-surface-container-high rounded-lg p-space-sm flex flex-col gap-space-sm">
          <div className="flex gap-space-sm flex-wrap items-center">
            <select
              value={contra}
              onChange={(e) => setContra(e.target.value)}
              className="flex-1 min-w-48 px-2.5 py-1.5 rounded-md bg-surface-container-lowest text-on-surface font-body-sm text-body-sm border border-outline-variant/40"
            >
              <option value="">Elige con qué comparar…</option>
              {otros.length > 0 && (
                <optgroup label="Otros documentos del caso">
                  {otros.map((a) => <option key={a.id} value={`a:${a.id}`}>{a.nombre_original}</option>)}
                </optgroup>
              )}
              {versiones.length > 0 && (
                <optgroup label="Versiones observadas de este documento">
                  {versiones.map((v) => <option key={v.id} value={`v:${v.id}`}>{v.nombre} · {v.subido_por_nombre}</option>)}
                </optgroup>
              )}
            </select>
            <button
              onClick={comparar}
              disabled={!contra || comparando}
              className="px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui disabled:opacity-60"
            >
              {comparando ? "Comparando…" : "Comparar"}
            </button>
          </div>
          {otros.length === 0 && versiones.length === 0 && (
            <p className="font-body-sm text-body-sm text-outline">
              No hay otro documento con texto leído ni versiones observadas para comparar.
            </p>
          )}

          {resultado && (
            <>
              <div className="flex items-center gap-space-md flex-wrap font-body-sm text-body-sm">
                <span className={`px-2 py-0.5 rounded font-label-ui text-label-ui ${resultado.cambios ? "bg-amber-400/10 text-amber-400" : "bg-tertiary/10 text-tertiary"}`}>
                  {resultado.cambios ? `${resultado.cambios} cambio(s)` : "Sin diferencias"}
                </span>
                <span className="text-on-surface-variant">Similitud {resultado.similitud}%</span>
                <span className="text-outline">
                  {resultado.palabras_a} → {resultado.palabras_b} palabras
                </span>
              </div>

              {resultado.cifras_cambiadas.length > 0 && (
                <div className="rounded-lg border border-error/30 bg-error/10 p-space-sm">
                  <p className="font-label-ui text-label-ui text-error mb-1 flex items-center gap-1">
                    <span className="material-symbols-outlined text-base">pin</span>
                    Cifras que cambiaron ({resultado.cifras_cambiadas.length})
                  </p>
                  <ul className="flex flex-col gap-0.5 font-label-code-sm text-label-code-sm">
                    {resultado.cifras_cambiadas.map((c, i) => (
                      <li key={i} className="flex items-center gap-2 flex-wrap">
                        <span className="line-through text-error">{c.antes || "—"}</span>
                        <span className="material-symbols-outlined text-sm text-outline">arrow_forward</span>
                        <span className="text-tertiary font-semibold">{c.despues || "(eliminado)"}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <p className="font-label-code-sm text-label-code-sm text-outline">
                <span className="text-error">rojo tachado</span> = está en «{resultado.a.nombre}» y no en la otra ·{" "}
                <span className="text-tertiary">verde</span> = aparece en «{resultado.b.nombre}»
              </p>
              <div className="max-h-96 overflow-auto rounded-md bg-surface-container-lowest p-space-sm font-body-sm text-body-sm leading-relaxed">
                {resultado.segmentos.map((s, i) => (
                  <Segmento key={i} s={s} expandido={expandidos[i]} onExpandir={() => setExpandidos({ ...expandidos, [i]: true })} />
                ))}
              </div>
              <p className="font-body-sm text-body-sm text-outline">
                Se ignoran mayúsculas y tildes para no confundir errores del OCR con cambios. Confirma cada diferencia
                mirando los documentos lado a lado.
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
