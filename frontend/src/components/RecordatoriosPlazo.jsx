import { useCallback, useEffect, useState } from "react";
import api from "../api";
import { useToast } from "./Toast";

// Sprint 6 (historia 26): plazos de pericias por vencer y recordatorios enviados.
// El backend los revisa solo cada hora; el botón fuerza la revisión (útil en la demo).

function restante(fecha) {
  const horas = Math.round((new Date(fecha) - new Date()) / 3600000);
  if (horas < 0) return "vencido";
  if (horas < 24) return `en ${horas} h`;
  return `en ${Math.floor(horas / 24)} d ${horas % 24} h`;
}

export default function RecordatoriosPlazo() {
  const [filas, setFilas] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const { notificar } = useToast();

  const cargar = useCallback(() => {
    api
      .get("/recordatorios-plazo")
      .then(({ data }) => setFilas(data))
      .catch(() => setFilas([]));
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const enviar = async () => {
    setEnviando(true);
    try {
      const { data } = await api.post("/recordatorios-plazo/enviar");
      notificar(
        data.enviados ? `${data.enviados} recordatorio(s) enviados por correo.` : "No hay plazos nuevos por recordar.",
        { tipo: data.enviados ? "success" : "info" }
      );
      cargar();
    } catch (err) {
      notificar(err.response?.data?.detail || "No se pudieron enviar los recordatorios.", { tipo: "error" });
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="bg-surface-container-low rounded-xl overflow-hidden">
      <div className="px-space-md py-3 flex flex-wrap items-center justify-between gap-space-sm">
        <div>
          <h2 className="font-headline-sm text-headline-sm text-on-surface">Plazos por vencer</h2>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            Se avisa por correo al perito y al fiscal 2 días antes de cada vencimiento.
          </p>
        </div>
        <button
          onClick={enviar}
          disabled={enviando}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui disabled:opacity-60"
        >
          <span className="material-symbols-outlined text-base">notifications_active</span>
          {enviando ? "Revisando..." : "Enviar recordatorios ahora"}
        </button>
      </div>
      {filas === null ? (
        <p className="px-space-md pb-3 font-body-sm text-body-sm text-on-surface-variant">Cargando...</p>
      ) : filas.length === 0 ? (
        <p className="px-space-md pb-3 font-body-sm text-body-sm text-outline">No hay plazos por vencer en los próximos 2 días.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-surface-container-lowest">
                {["Pericia", "Plazo", "Vence", "Recordatorio"].map((h) => (
                  <th key={h} className="px-space-md py-2 font-label-ui text-label-ui text-outline uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filas.map((f) => (
                <tr key={`${f.pericia_id}-${f.tipo}-${f.vence_en}`} className="border-t border-outline-variant/20">
                  <td className="px-space-md py-2">
                    <div className="font-label-code-sm text-label-code-sm text-on-surface">{f.pericia_codigo}</div>
                    <div className="font-body-sm text-body-sm text-on-surface-variant">{f.caso_numero}</div>
                  </td>
                  <td className="px-space-md py-2 font-body-sm text-body-sm text-on-surface">{f.tipo_etiqueta}</td>
                  <td className="px-space-md py-2 font-body-sm text-body-sm text-on-surface">
                    {new Date(f.vence_en).toLocaleString("es-PE")}
                    <span className="block text-on-surface-variant">{restante(f.vence_en)}</span>
                  </td>
                  <td className="px-space-md py-2 font-body-sm text-body-sm">
                    {f.recordado_en ? (
                      <span className="text-tertiary">
                        Enviado {new Date(f.recordado_en).toLocaleString("es-PE")}
                        <span className="block text-on-surface-variant">{f.destinatarios.join(", ")}</span>
                      </span>
                    ) : (
                      <span className="text-outline">Pendiente</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}