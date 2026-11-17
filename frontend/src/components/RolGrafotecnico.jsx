import { useState } from "react";
import api from "../api";
import { useToast } from "./Toast";
import { ROLES_GRAFOTECNICOS } from "../grafotecnia";

// Sprint 7 (historia 28): en grafotecnia, cada documento es DUBITADO (el cuestionado) o
// INDUBITADO (de autoría conocida, el patrón con el que se compara).

export function InsigniaRol({ rol }) {
  const r = ROLES_GRAFOTECNICOS[rol];
  if (!r) return null;
  return (
    <span title={r.ayuda} className={`px-2 py-0.5 rounded border font-label-ui text-label-ui uppercase tracking-wider ${r.clase}`}>
      {r.texto}
    </span>
  );
}

export default function RolGrafotecnico({ archivo, puedeEditar, onCambio, onHistorial }) {
  const [guardando, setGuardando] = useState(false);
  const { notificar } = useToast();

  const marcar = async (rol) => {
    setGuardando(true);
    try {
      await api.patch(`/archivos/${archivo.id}/grafotecnia`, { rol });
      notificar(rol ? `Marcado como ${ROLES_GRAFOTECNICOS[rol].texto.toLowerCase()}.` : "Se quitó la clasificación.", { tipo: "success" });
      onCambio?.();
      onHistorial?.();
    } catch (err) {
      notificar(err.response?.data?.detail || "No se pudo clasificar el documento.", { tipo: "error" });
    } finally {
      setGuardando(false);
    }
  };

  const opcion = (rol, texto) => (
    <button
      key={texto}
      disabled={guardando || archivo.rol_grafotecnico === rol}
      onClick={() => marcar(rol)}
      className={`px-3 py-1.5 font-label-ui text-label-ui border-outline-variant/40 disabled:cursor-default ${
        archivo.rol_grafotecnico === rol
          ? "bg-primary text-on-primary"
          : "bg-surface-container-high text-on-surface hover:bg-surface-container disabled:opacity-60"
      }`}
    >
      {texto}
    </button>
  );

  return (
    <div>
      <span className="font-label-ui text-label-ui text-outline uppercase tracking-wider block mb-1">
        Grafotecnia
      </span>
      {puedeEditar ? (
        <div className="flex items-center gap-space-sm flex-wrap">
          <div className="inline-flex rounded-lg overflow-hidden border border-outline-variant/40 divide-x divide-outline-variant/40">
            {opcion("dubitado", "Dubitado")}
            {opcion("indubitado", "Indubitado")}
            {opcion(null, "Sin clasificar")}
          </div>
          <span className="font-body-sm text-body-sm text-on-surface-variant">
            {ROLES_GRAFOTECNICOS[archivo.rol_grafotecnico]?.ayuda || "Indica si es el documento cuestionado o un patrón."}
          </span>
        </div>
      ) : (
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          {archivo.rol_grafotecnico ? <InsigniaRol rol={archivo.rol_grafotecnico} /> : "Sin clasificar."}
        </p>
      )}
    </div>
  );
}
