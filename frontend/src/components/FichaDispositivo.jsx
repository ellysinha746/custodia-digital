import { useState } from "react";
import api from "../api";
import { useToast } from "./Toast";

// Sprint 4 (historias 13 y 17): ficha del dispositivo de origen.
const CAMPOS = [
  { clave: "imei", etiqueta: "IMEI", placeholder: "15 dígitos" },
  { clave: "modelo", etiqueta: "Modelo", placeholder: "Ej. Samsung Galaxy S21" },
  { clave: "mac", etiqueta: "Dirección MAC", placeholder: "AA:BB:CC:DD:EE:FF" },
  { clave: "sistema_operativo", etiqueta: "Sistema operativo", placeholder: "Ej. Android 14" },
];

const VACIA = { imei: "", modelo: "", mac: "", sistema_operativo: "" };

const ESTADO_CAMPO = {
  coincide: { texto: "Coincide", clase: "text-tertiary", icono: "check_circle" },
  distinto: { texto: "Distinto", clase: "text-error", icono: "cancel" },
  no_verificado: { texto: "No verificado", clase: "text-outline", icono: "remove" },
  sin_registro: { texto: "Sin registro", clase: "text-outline", icono: "help" },
};

const claseInput =
  "px-2.5 py-1.5 rounded-md bg-surface-container-lowest text-on-surface font-body-sm text-body-sm placeholder:text-outline/50 focus:outline-none focus:ring-1 focus:ring-primary/50";

/** Los 4 inputs de la ficha. Se usa al subir evidencia y en los formularios de abajo. */
export function CamposFicha({ valor, onChange }) {
  return (
    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-space-sm">
      {CAMPOS.map((c) => (
        <label key={c.clave} className="flex flex-col gap-1">
          <span className="font-label-code-sm text-label-code-sm text-outline">{c.etiqueta}</span>
          <input
            value={valor[c.clave] ?? ""}
            onChange={(e) => onChange({ ...valor, [c.clave]: e.target.value })}
            placeholder={c.placeholder}
            className={claseInput}
          />
        </label>
      ))}
    </div>
  );
}

function limpiar(ficha) {
  const salida = {};
  Object.entries(ficha).forEach(([k, v]) => {
    if (v && v.trim()) salida[k] = v.trim();
  });
  return salida;
}

export default function FichaDispositivo({ archivo, puedeEscribir, onCambio, onHistorial }) {
  const [modo, setModo] = useState(null); // null | "registrar" | "verificar"
  const [form, setForm] = useState(VACIA);
  const [enviando, setEnviando] = useState(false);
  const [comparacion, setComparacion] = useState(null);
  const { notificar } = useToast();

  const ficha = archivo.ficha_dispositivo;

  const abrir = (nuevoModo) => {
    setForm(VACIA);
    setComparacion(null);
    setModo(nuevoModo);
  };

  const registrar = async (e) => {
    e.preventDefault();
    setEnviando(true);
    try {
      await api.put(`/archivos/${archivo.id}/ficha`, limpiar(form));
      notificar("Ficha del dispositivo registrada.", { tipo: "success" });
      setModo(null);
      onCambio();
      onHistorial();
    } catch (err) {
      notificar(err.response?.data?.detail || "No se pudo registrar la ficha.", { tipo: "error" });
    } finally {
      setEnviando(false);
    }
  };

  const verificar = async (e) => {
    e.preventDefault();
    setEnviando(true);
    try {
      const { data } = await api.post(`/archivos/${archivo.id}/verificar-dispositivo`, limpiar(form));
      setComparacion(data);
      notificar(
        data.resultado === "dispositivo_coincide"
          ? "El dispositivo coincide con la ficha registrada."
          : "¡El dispositivo NO coincide! Se registró una alerta.",
        { tipo: data.resultado === "dispositivo_coincide" ? "success" : "error" }
      );
      onHistorial();
    } catch (err) {
      notificar(err.response?.data?.detail || "No se pudo verificar el dispositivo.", { tipo: "error" });
    } finally {
      setEnviando(false);
    }
  };

  const exportar = async (formato) => {
    try {
      const { data } = await api.get(`/archivos/${archivo.id}/ficha/exportar`, {
        params: { formato },
        responseType: "blob",
      });
      const url = URL.createObjectURL(data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ficha_${archivo.nombre_original}.${formato}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      onHistorial();
    } catch {
      notificar("No se pudo exportar la ficha.", { tipo: "error" });
    }
  };

  const botonChico =
    "inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-surface-container-high text-on-surface font-label-ui text-label-ui hover:bg-surface-container";

  return (
    <div>
      <div className="flex items-center justify-between mb-1 gap-2 flex-wrap">
        <span className="font-label-ui text-label-ui text-outline uppercase tracking-wider">
          Ficha del dispositivo
        </span>
        <div className="flex gap-1.5 flex-wrap">
          {ficha ? (
            <>
              <button onClick={() => abrir(modo === "verificar" ? null : "verificar")} className={botonChico}>
                <span className="material-symbols-outlined text-base">compare_arrows</span>
                Verificar dispositivo
              </button>
              <button onClick={() => exportar("json")} className={botonChico}>
                <span className="material-symbols-outlined text-base">data_object</span>
                JSON
              </button>
              <button onClick={() => exportar("csv")} className={botonChico}>
                <span className="material-symbols-outlined text-base">table</span>
                CSV
              </button>
            </>
          ) : (
            puedeEscribir &&
            modo !== "registrar" && (
              <button
                onClick={() => abrir("registrar")}
                className="font-label-ui text-label-ui text-primary hover:underline"
              >
                Registrar ficha
              </button>
            )
          )}
        </div>
      </div>

      {ficha ? (
        <dl className="grid sm:grid-cols-2 gap-x-space-md gap-y-1">
          {CAMPOS.map((c) => (
            <div key={c.clave} className="flex justify-between sm:justify-start sm:gap-2">
              <dt className="font-body-sm text-body-sm text-on-surface-variant">{c.etiqueta}:</dt>
              <dd className="font-label-code-sm text-label-code-sm text-on-surface">{ficha[c.clave] || "—"}</dd>
            </div>
          ))}
          {archivo.ficha_registrada_en && (
            <p className="sm:col-span-2 font-label-code-sm text-label-code-sm text-outline mt-1">
              Registrada el{" "}
              {new Date(archivo.ficha_registrada_en).toLocaleString("es-PE", {
                dateStyle: "medium",
                timeStyle: "short",
              })}{" "}
              · no se puede modificar
            </p>
          )}
        </dl>
      ) : (
        modo !== "registrar" && (
          <p className="font-body-sm text-body-sm text-outline">Sin ficha del dispositivo registrada.</p>
        )
      )}

      {modo && (
        <form
          onSubmit={modo === "registrar" ? registrar : verificar}
          className="mt-space-sm flex flex-col gap-space-sm bg-surface-container-high rounded-lg p-space-sm"
        >
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            {modo === "registrar"
              ? "Una vez registrada, la ficha queda fija y se usa como referencia en verificaciones posteriores."
              : "Ingresa los datos que lees hoy del dispositivo. Se comparan con la ficha registrada en la subida."}
          </p>
          <CamposFicha valor={form} onChange={setForm} />
          <div className="flex justify-end gap-space-sm">
            <button
              type="button"
              onClick={() => setModo(null)}
              className="px-3 py-1.5 rounded-lg font-label-ui text-label-ui text-on-surface-variant hover:bg-surface-container"
            >
              Cerrar
            </button>
            <button
              type="submit"
              disabled={enviando}
              className="px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui disabled:opacity-60"
            >
              {enviando ? "Enviando..." : modo === "registrar" ? "Registrar" : "Comparar"}
            </button>
          </div>

          {comparacion && (
            <table className="w-full text-left mt-1">
              <thead>
                <tr>
                  {["Campo", "Registrado", "Verificado hoy", "Resultado"].map((h) => (
                    <th key={h} className="py-1 pr-3 font-label-ui text-label-ui text-outline uppercase tracking-wider">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comparacion.campos.map((c) => {
                  const est = ESTADO_CAMPO[c.estado];
                  return (
                    <tr key={c.campo} className="border-t border-outline-variant/20">
                      <td className="py-1.5 pr-3 font-body-sm text-body-sm text-on-surface-variant">{c.etiqueta}</td>
                      <td className="py-1.5 pr-3 font-label-code-sm text-label-code-sm text-on-surface">
                        {c.registrado || "—"}
                      </td>
                      <td className="py-1.5 pr-3 font-label-code-sm text-label-code-sm text-on-surface">
                        {c.actual || "—"}
                      </td>
                      <td className={`py-1.5 font-label-ui text-label-ui ${est.clase}`}>
                        <span className="inline-flex items-center gap-1">
                          <span className="material-symbols-outlined text-base">{est.icono}</span>
                          {est.texto}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </form>
      )}
    </div>
  );
}