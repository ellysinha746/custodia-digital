import { useCallback, useEffect, useState } from "react";
import api from "../api";
import { useToast } from "./Toast";

// Sprint 4 (historia 14): versiones de un archivo con observaciones de otro
// perito. Se guardan aparte: la evidencia original y su copia no se tocan.

async function bajarBlob(url, nombre) {
  const { data } = await api.get(url, { responseType: "blob" });
  const enlace = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = enlace;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(enlace);
}

export default function VersionesObservadas({ archivo, puedeEscribir, onHistorial }) {
  const [versiones, setVersiones] = useState(null);
  const [abierto, setAbierto] = useState(false);
  const [seleccionado, setSeleccionado] = useState(null);
  const [observaciones, setObservaciones] = useState("");
  const [enviando, setEnviando] = useState(false);
  const { notificar } = useToast();

  const cargar = useCallback(async () => {
    try {
      const { data } = await api.get(`/archivos/${archivo.id}/observadas`);
      setVersiones(data);
    } catch {
      setVersiones([]);
    }
  }, [archivo.id]);

  useEffect(() => {
    // La carga ocurre después del await: no hay render en cascada.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    cargar();
  }, [cargar]);

  const subir = async (e) => {
    e.preventDefault();
    if (!seleccionado) return;
    setEnviando(true);
    const datos = new FormData();
    datos.append("archivo", seleccionado);
    datos.append("observaciones", observaciones);
    try {
      await api.post(`/archivos/${archivo.id}/observadas`, datos);
      notificar("Versión observada registrada. El original no se modificó.", { tipo: "success" });
      setAbierto(false);
      setSeleccionado(null);
      setObservaciones("");
      cargar();
      onHistorial();
    } catch (err) {
      notificar(err.response?.data?.detail || "No se pudo subir la versión observada.", { tipo: "error" });
    } finally {
      setEnviando(false);
    }
  };

  const descargar = async (v) => {
    try {
      await bajarBlob(`/observadas/${v.id}/descargar`, `OBSERVADA_${v.nombre}`);
      onHistorial();
    } catch {
      notificar("No se pudo descargar la versión observada.", { tipo: "error" });
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="font-label-ui text-label-ui text-outline uppercase tracking-wider">
          Versiones observadas {versiones ? `(${versiones.length})` : ""}
        </span>
        {puedeEscribir && !abierto && (
          <button
            onClick={() => setAbierto(true)}
            className="font-label-ui text-label-ui text-primary hover:underline"
          >
            Subir versión observada
          </button>
        )}
      </div>

      {abierto && (
        <form
          onSubmit={subir}
          className="flex flex-col gap-space-sm bg-surface-container-high rounded-lg p-space-sm mb-space-sm"
        >
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            Sube la versión con las observaciones de otro perito. Se guarda aparte: el original y la copia de
            trabajo no se modifican.
          </p>
          <input
            type="file"
            required
            onChange={(e) => setSeleccionado(e.target.files[0])}
            className="font-body-sm text-body-sm text-on-surface-variant file:mr-3 file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:bg-surface-container-lowest file:text-on-surface file:font-label-ui file:text-label-ui"
          />
          <textarea
            required
            rows={3}
            value={observaciones}
            onChange={(e) => setObservaciones(e.target.value)}
            placeholder="Observaciones del perito (qué se marcó, qué se encontró)..."
            className="px-2.5 py-1.5 rounded-md bg-surface-container-lowest text-on-surface font-body-sm text-body-sm placeholder:text-outline/50 focus:outline-none focus:ring-1 focus:ring-primary/50"
          />
          <div className="flex justify-end gap-space-sm">
            <button
              type="button"
              onClick={() => setAbierto(false)}
              className="px-3 py-1.5 rounded-lg font-label-ui text-label-ui text-on-surface-variant hover:bg-surface-container"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={enviando || !seleccionado || !observaciones.trim()}
              className="px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui disabled:opacity-60"
            >
              {enviando ? "Subiendo..." : "Guardar versión"}
            </button>
          </div>
        </form>
      )}

      {!versiones ? (
        <p className="font-body-sm text-body-sm text-outline">Cargando...</p>
      ) : versiones.length === 0 ? (
        <p className="font-body-sm text-body-sm text-outline">Ningún perito ha subido observaciones todavía.</p>
      ) : (
        <ul className="flex flex-col gap-space-sm">
          {versiones.map((v) => (
            <li key={v.id} className="bg-surface-container-high rounded-lg p-space-sm flex items-start justify-between gap-space-md">
              <div className="min-w-0">
                <p className="font-body-sm text-body-sm text-on-surface">{v.observaciones}</p>
                <p className="mt-1 font-label-code-sm text-label-code-sm text-outline truncate">
                  {v.nombre} · {v.subido_por_nombre} ·{" "}
                  {new Date(v.subido_en).toLocaleString("es-PE", { dateStyle: "medium", timeStyle: "short" })} ·
                  SHA-256 {v.hash_sha256.slice(0, 12)}…
                </p>
              </div>
              <button
                onClick={() => descargar(v)}
                className="shrink-0 inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-surface-container-lowest text-on-surface font-label-ui text-label-ui hover:bg-surface-container"
              >
                <span className="material-symbols-outlined text-base">rate_review</span>
                Descargar observada
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}