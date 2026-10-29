import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import Layout from "../components/Layout";
import { useToast } from "../components/Toast";

const ESPECIALIDADES = {
  audio: "Audio",
  video: "Video",
  informatica: "Informática",
  telefonia: "Telefonía",
};

export default function Papelera() {
  const [casos, setCasos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const navigate = useNavigate();
  const { notificar } = useToast();

  const cargar = async () => {
    try {
      const { data } = await api.get("/casos/papelera");
      setCasos(data);
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
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const restaurar = async (id, numero) => {
    try {
      await api.post(`/casos/${id}/restaurar`);
      setCasos((prev) => prev.filter((c) => c.id !== id));
      notificar(`Caso ${numero} restaurado.`, { tipo: "success" });
    } catch {
      notificar("No se pudo restaurar el caso.", { tipo: "error" });
    }
  };

  return (
    <Layout>
      <div className="mb-space-lg">
        <h1 className="font-headline-lg text-headline-lg text-on-surface">Papelera</h1>
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          Los casos eliminados se guardan aquí 30 días antes de borrarse en forma definitiva.
        </p>
      </div>

      <div className="bg-surface-container-low rounded-xl overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-surface-container-lowest">
              {["Número de caso", "Especialidad", "Eliminado", "Días restantes", ""].map((h) => (
                <th key={h} className="px-space-md py-3 font-label-ui text-label-ui text-outline uppercase tracking-wider">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {casos.map((c) => (
              <tr key={c.id} className="border-t border-outline-variant/20">
                <td className="px-space-md py-4 font-label-code-lg text-label-code-lg text-on-surface">
                  {c.numero_caso}
                </td>
                <td className="px-space-md py-4 font-body-sm text-body-sm text-on-surface-variant">
                  {ESPECIALIDADES[c.especialidad]}
                </td>
                <td className="px-space-md py-4 font-body-sm text-body-sm text-on-surface-variant">
                  {new Date(c.eliminado_en).toLocaleDateString("es-PE", { dateStyle: "medium" })}
                </td>
                <td className="px-space-md py-4">
                  <span
                    className={`font-label-ui text-label-ui uppercase tracking-wider ${
                      c.dias_restantes <= 5 ? "text-error" : "text-on-surface-variant"
                    }`}
                  >
                    {c.dias_restantes} día(s)
                  </span>
                </td>
                <td className="px-space-md py-4 text-right">
                  <button
                    onClick={() => restaurar(c.id, c.numero_caso)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-high text-primary font-label-ui text-label-ui hover:bg-surface-container"
                  >
                    <span className="material-symbols-outlined text-base">restore_from_trash</span>
                    Restaurar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {!cargando && casos.length === 0 && (
          <div className="py-16 flex flex-col items-center text-on-surface-variant">
            <span className="material-symbols-outlined text-5xl text-outline mb-2">delete_sweep</span>
            <p className="font-body-md text-body-md">La papelera está vacía.</p>
          </div>
        )}
      </div>
    </Layout>
  );
}
