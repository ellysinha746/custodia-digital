import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import Layout from "../components/Layout";

// Sprint 5 (historia 19.2): padrón de peritos oficiales y de parte.

const ESPECIALIDADES = { audio: "Audio", video: "Video", informatica: "Informática", telefonia: "Telefonía" };

function Chip({ activo, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-full font-label-code-sm text-label-code-sm ${
        activo ? "bg-primary/15 text-primary ring-1 ring-primary/40" : "bg-surface-container text-on-surface-variant hover:bg-surface-container-high"
      }`}
    >
      {children}
    </button>
  );
}

export default function Peritos() {
  const [peritos, setPeritos] = useState([]);
  const [tipo, setTipo] = useState("");
  const [especialidad, setEspecialidad] = useState("");
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    let activo = true;
    const t = setTimeout(() => {
      api
        .get("/peritos", { params: { ...(tipo && { tipo }), ...(especialidad && { especialidad }), ...(q.trim() && { q: q.trim() }) } })
        .then(({ data }) => activo && setPeritos(data))
        .catch((err) => {
          if (err.response?.status === 401) {
            localStorage.clear();
            navigate("/");
          } else if (activo) setError(err.response?.data?.detail || "No se pudo cargar el padrón.");
        });
    }, 200);
    return () => {
      activo = false;
      clearTimeout(t);
    };
  }, [tipo, especialidad, q, navigate]);

  return (
    <Layout>
      <div className="mb-space-lg">
        <h1 className="font-headline-lg text-headline-lg text-on-surface">Padrón de peritos</h1>
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          Peritos oficiales y de parte registrados. Los altas y cambios de ficha se hacen en Usuarios.
        </p>
      </div>

      {error && <p className="text-error font-body-sm text-body-sm mb-space-md">{error}</p>}

      <div className="bg-surface-container-low rounded-xl p-space-md mb-space-md flex flex-col gap-space-sm">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por nombre, institución o N° de registro…"
          className="px-3 py-2 rounded-lg bg-surface-container-lowest text-on-surface font-body-sm text-body-sm focus:outline-none focus:ring-1 focus:ring-primary/50" />
        <div className="flex flex-wrap gap-2 items-center">
          <span className="font-label-ui text-label-ui text-outline uppercase tracking-wider mr-1">Tipo</span>
          <Chip activo={!tipo} onClick={() => setTipo("")}>Todos</Chip>
          <Chip activo={tipo === "perito"} onClick={() => setTipo("perito")}>Oficiales</Chip>
          <Chip activo={tipo === "perito_parte"} onClick={() => setTipo("perito_parte")}>De parte</Chip>
          <span className="font-label-ui text-label-ui text-outline uppercase tracking-wider ml-3 mr-1">Especialidad</span>
          <Chip activo={!especialidad} onClick={() => setEspecialidad("")}>Todas</Chip>
          {Object.entries(ESPECIALIDADES).map(([k, v]) => (
            <Chip key={k} activo={especialidad === k} onClick={() => setEspecialidad(k)}>{v}</Chip>
          ))}
        </div>
      </div>

      <div className="bg-surface-container-low rounded-xl overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-surface-container-lowest">
              {["Perito", "Tipo", "Especialidad", "Institución", "Registro / colegiatura", "Pericias activas", "Estado"].map((h) => (
                <th key={h} className="px-space-md py-3 font-label-ui text-label-ui text-outline uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {peritos.map((p) => (
              <tr key={p.id} onClick={() => navigate(`/peritos/${p.id}`)} className="border-t border-outline-variant/20 cursor-pointer hover:bg-surface-container">
                <td className="px-space-md py-3">
                  <div className="font-body-sm text-body-sm text-on-surface font-semibold">{p.nombre}</div>
                  <div className="font-label-code-sm text-label-code-sm text-outline">{p.email}{p.telefono ? ` · ${p.telefono}` : ""}</div>
                </td>
                <td className="px-space-md py-3">
                  <span className={`px-2 py-0.5 rounded font-label-ui text-label-ui ${p.tipo === "perito" ? "bg-primary/10 text-primary" : "bg-secondary/10 text-secondary"}`}>
                    {p.tipo_etiqueta}
                  </span>
                </td>
                <td className="px-space-md py-3 font-body-sm text-body-sm text-on-surface-variant">{ESPECIALIDADES[p.especialidad]}</td>
                <td className="px-space-md py-3 font-body-sm text-body-sm text-on-surface-variant">{p.institucion || "—"}</td>
                <td className="px-space-md py-3 font-label-code-sm text-label-code-sm text-on-surface">{p.registro_profesional || "—"}</td>
                <td className="px-space-md py-3 font-label-code-sm text-label-code-sm text-on-surface">{p.pericias_activas}</td>
                <td className="px-space-md py-3">
                  <span className={`font-label-ui text-label-ui ${p.habilitado ? "text-tertiary" : "text-error"}`}>
                    {p.habilitado ? "Habilitado" : "Inhabilitado"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {peritos.length === 0 && !error && (
          <p className="py-12 text-center font-body-md text-body-md text-on-surface-variant">No hay peritos con esos filtros.</p>
        )}
      </div>
    </Layout>
  );
}
