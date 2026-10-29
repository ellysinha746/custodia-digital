import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import Layout from "../components/Layout";

const ACCIONES = {
  subida: { label: "Subida", icono: "upload_file", color: "text-secondary" },
  acceso: { label: "Acceso", icono: "visibility", color: "text-outline" },
  descarga: { label: "Descarga", icono: "download", color: "text-primary" },
  verificacion: { label: "Verificación", icono: "verified", color: "text-tertiary" },
};

function Chip({ activo, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-full font-label-code-sm text-label-code-sm transition-colors ${
        activo
          ? "bg-primary/15 text-primary ring-1 ring-primary/40"
          : "bg-surface-container text-on-surface-variant hover:bg-surface-container-high"
      }`}
    >
      {children}
    </button>
  );
}

export default function Auditoria() {
  const [eventos, setEventos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [filtro, setFiltro] = useState("");
  const navigate = useNavigate();

  const cargar = async (accion) => {
    setCargando(true);
    try {
      const { data } = await api.get("/auditoria", { params: accion ? { accion } : {} });
      setEventos(data);
    } catch (err) {
      if (err.response?.status === 401) {
        localStorage.clear();
        navigate("/");
      }
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargar(filtro || undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtro]);

  return (
    <Layout>
      <div className="mb-space-lg">
        <h1 className="font-headline-lg text-headline-lg text-on-surface">Auditoría</h1>
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          Todos los eventos de custodia registrados en el sistema.
        </p>
      </div>

      <div className="flex flex-wrap gap-space-sm mb-space-md">
        <Chip activo={!filtro} onClick={() => setFiltro("")}>Todas</Chip>
        {Object.entries(ACCIONES).map(([k, v]) => (
          <Chip key={k} activo={filtro === k} onClick={() => setFiltro(k)}>{v.label}</Chip>
        ))}
      </div>

      <div className="bg-surface-container-low rounded-xl overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-surface-container-lowest">
              {["Fecha", "Acción", "Usuario", "Caso", "Archivo", "Resultado"].map((h) => (
                <th key={h} className="px-space-md py-3 font-label-ui text-label-ui text-outline uppercase tracking-wider">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {eventos.map((ev) => {
              const info = ACCIONES[ev.accion];
              return (
                <tr
                  key={ev.id}
                  onClick={() => navigate(`/casos/${ev.caso_id}`)}
                  className="cursor-pointer hover:bg-surface-container transition-colors border-t border-outline-variant/20"
                >
                  <td className="px-space-md py-3 font-label-code-sm text-label-code-sm text-outline whitespace-nowrap">
                    {new Date(ev.fecha).toLocaleString("es-PE", { dateStyle: "medium", timeStyle: "short" })}
                  </td>
                  <td className="px-space-md py-3">
                    <span className={`inline-flex items-center gap-1.5 font-label-ui text-label-ui uppercase tracking-wider ${info.color}`}>
                      <span className="material-symbols-outlined text-base">{info.icono}</span>
                      {info.label}
                    </span>
                  </td>
                  <td className="px-space-md py-3 font-body-sm text-body-sm text-on-surface">{ev.usuario_nombre}</td>
                  <td className="px-space-md py-3 font-label-code-sm text-label-code-sm text-on-surface">{ev.caso_numero}</td>
                  <td className="px-space-md py-3 font-body-sm text-body-sm text-on-surface-variant truncate max-w-xs">
                    {ev.archivo_nombre}
                  </td>
                  <td className="px-space-md py-3">
                    {ev.resultado && (
                      <span
                        className={`font-label-code-sm text-label-code-sm px-1.5 py-0.5 rounded ${
                          ev.resultado === "alterado"
                            ? "bg-error/15 text-error"
                            : "bg-surface-container-high text-on-surface-variant"
                        }`}
                      >
                        {ev.resultado}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {!cargando && eventos.length === 0 && (
          <div className="py-16 flex flex-col items-center text-on-surface-variant">
            <span className="material-symbols-outlined text-5xl text-outline mb-2">history_toggle_off</span>
            <p className="font-body-md text-body-md">Todavía no hay eventos registrados.</p>
          </div>
        )}
      </div>
    </Layout>
  );
}
