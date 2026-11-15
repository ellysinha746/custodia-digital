import { useRef, useState } from "react";
import api from "../api";
import { useToast } from "./Toast";

// Sprint 4 (historia 16): exportar el panel de auditoría con sello de tiempo
// y verificar que un reporte descargado es auténtico.

export default function ReporteAuditoria({ filtro }) {
  const [exportando, setExportando] = useState(null);
  const [verificacion, setVerificacion] = useState(null);
  const inputRef = useRef(null);
  const { notificar } = useToast();

  const exportar = async (formato) => {
    setExportando(formato);
    try {
      const { data, headers } = await api.get("/auditoria/reporte", {
        params: { formato, ...(filtro ? { accion: filtro } : {}) },
        responseType: "blob",
      });
      const folio = headers["x-folio"] || "reporte";
      const enlace = URL.createObjectURL(data);
      const a = document.createElement("a");
      a.href = enlace;
      a.download = `reporte_auditoria_${folio}.${formato}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(enlace);
      // Sprint 6 (historia 21): avisa si se obtuvo el sello RFC 3161 de la autoridad externa.
      notificar(
        headers["x-sello-tsa"] === "si"
          ? `Reporte ${folio} emitido con sello del servidor y sello RFC 3161 de FreeTSA.`
          : `Reporte ${folio} emitido con sello del servidor. FreeTSA no respondió: va sin sello RFC 3161.`,
        { tipo: headers["x-sello-tsa"] === "si" ? "success" : "info" }
      );
    } catch {
      notificar("No se pudo exportar el reporte.", { tipo: "error" });
    } finally {
      setExportando(null);
    }
  };

  const verificar = async (e) => {
    const archivo = e.target.files[0];
    e.target.value = "";
    if (!archivo) return;
    const datos = new FormData();
    datos.append("archivo", archivo);
    try {
      const { data } = await api.post("/auditoria/reporte/verificar", datos);
      setVerificacion({ ...data, nombre: archivo.name });
    } catch {
      notificar("No se pudo verificar el reporte.", { tipo: "error" });
    }
  };

  // Sprint 6 (historia 21): ZIP con el sello .tsr, los datos sellados y los certificados de FreeTSA.
  const bajarSello = async (folio) => {
    try {
      const { data } = await api.get(`/auditoria/reporte/${encodeURIComponent(folio)}/sello-tiempo`, { responseType: "blob" });
      const enlace = URL.createObjectURL(data);
      const a = document.createElement("a");
      a.href = enlace;
      a.download = `sello_rfc3161_${folio}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(enlace);
    } catch {
      notificar("No se pudo descargar el sello (solo lo descarga quien emitió el reporte, el jefe o el fiscal).", { tipo: "error" });
    }
  };

  const boton =
    "inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-surface-container-high text-on-surface font-label-ui text-label-ui hover:bg-surface-container disabled:opacity-60";

  return (
    <div className="flex flex-col items-end gap-space-sm">
      <div className="flex flex-wrap gap-space-sm justify-end">
        <button onClick={() => exportar("pdf")} disabled={!!exportando} className={boton}>
          <span className="material-symbols-outlined text-base">picture_as_pdf</span>
          {exportando === "pdf" ? "Generando..." : "Exportar PDF"}
        </button>
        <button onClick={() => exportar("csv")} disabled={!!exportando} className={boton}>
          <span className="material-symbols-outlined text-base">table</span>
          {exportando === "csv" ? "Generando..." : "Exportar CSV"}
        </button>
        <button onClick={() => inputRef.current?.click()} className={boton}>
          <span className="material-symbols-outlined text-base">verified</span>
          Verificar reporte
        </button>
        <input ref={inputRef} type="file" accept=".pdf,.csv" onChange={verificar} className="hidden" />
      </div>

      {verificacion && (
        <div
          className={`w-full max-w-xl rounded-lg px-space-md py-3 border flex items-start gap-2.5 ${
            verificacion.valido ? "border-tertiary/40 bg-tertiary/10" : "border-error/40 bg-error/10"
          }`}
        >
          <span className={`material-symbols-outlined ${verificacion.valido ? "text-tertiary" : "text-error"}`}>
            {verificacion.valido ? "verified" : "gpp_bad"}
          </span>
          <div className="flex-1 min-w-0">
            <p className="font-body-sm text-body-sm text-on-surface font-semibold">
              {verificacion.valido ? "Reporte auténtico" : "Reporte NO válido"}
            </p>
            <p className="font-body-sm text-body-sm text-on-surface-variant">{verificacion.mensaje}</p>
            {verificacion.valido && (
              <p className="mt-1 font-label-code-sm text-label-code-sm text-outline">
                Folio {verificacion.folio} · {verificacion.formato?.toUpperCase()} · emitido{" "}
                {new Date(verificacion.generado_en).toLocaleString("es-PE")} por {verificacion.generado_por} ·{" "}
                {verificacion.total_eventos} evento(s)
              </p>
            )}
            {/* Sprint 6 (historia 21): sello de tiempo RFC 3161 de la autoridad externa */}
            {verificacion.valido && verificacion.sello_tsa && (
              <div className="mt-2 flex items-start gap-1.5">
                <span
                  className={`material-symbols-outlined text-base ${
                    !verificacion.sello_tsa.presente ? "text-outline" : verificacion.sello_tsa.valido ? "text-tertiary" : "text-error"
                  }`}
                >
                  schedule
                </span>
                <div className="min-w-0">
                  <p className="font-body-sm text-body-sm text-on-surface-variant">{verificacion.sello_tsa.mensaje}</p>
                  {verificacion.sello_tsa.presente && (
                    <p className="font-label-code-sm text-label-code-sm text-outline">
                      {verificacion.sello_tsa.tsa} · {new Date(verificacion.sello_tsa.fecha).toLocaleString("es-PE")} · N°{" "}
                      {verificacion.sello_tsa.serie} ·{" "}
                      <button onClick={() => bajarSello(verificacion.folio)} className="text-primary hover:underline">
                        descargar sello para OpenSSL
                      </button>
                    </p>
                  )}
                </div>
              </div>
            )}
            <p className="mt-1 font-label-code-sm text-label-code-sm text-outline truncate">Archivo: {verificacion.nombre}</p>
          </div>
          <button onClick={() => setVerificacion(null)} className="text-outline hover:text-on-surface">
            <span className="material-symbols-outlined text-base">close</span>
          </button>
        </div>
      )}
    </div>
  );
}