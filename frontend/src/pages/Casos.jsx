import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import Layout from "../components/Layout";
import { useToast } from "../components/Toast";

const ESPECIALIDADES = {
  audio: { label: "Audio", icon: "graphic_eq" },
  video: { label: "Video", icon: "videocam" },
  informatica: { label: "Informática", icon: "computer" },
  telefonia: { label: "Telefonía", icon: "smartphone" },
};

const ESTADOS = {
  abierto: { label: "Abierto", text: "text-tertiary", dot: "bg-tertiary" },
  en_proceso: { label: "En proceso", text: "text-amber-400", dot: "bg-amber-400 animate-pulse" },
  cerrado: { label: "Cerrado", text: "text-outline", dot: "bg-outline" },
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

export default function Casos() {
  const [casos, setCasos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [busqueda, setBusqueda] = useState("");
  const [filtroEsp, setFiltroEsp] = useState("");
  const [filtroEst, setFiltroEst] = useState("");
  const [modal, setModal] = useState(false);
  const [numero, setNumero] = useState("");
  const [especialidad, setEspecialidad] = useState("informatica");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const navigate = useNavigate();
  const { notificar } = useToast();

  const cargar = async () => {
    try {
      const { data } = await api.get("/casos");
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
  }, []);

  const visibles = useMemo(
    () =>
      casos.filter(
        (c) =>
          (!filtroEsp || c.especialidad === filtroEsp) &&
          (!filtroEst || c.estado === filtroEst) &&
          c.numero_caso.toLowerCase().includes(busqueda.toLowerCase())
      ),
    [casos, filtroEsp, filtroEst, busqueda]
  );

  const contar = (estado) => casos.filter((c) => c.estado === estado).length;

  const tarjetas = [
    { titulo: "Total de casos", valor: casos.length, icono: "folder_special", color: "text-primary" },
    { titulo: "Abiertos", valor: contar("abierto"), icono: "folder_open", color: "text-tertiary" },
    { titulo: "En proceso", valor: contar("en_proceso"), icono: "pending_actions", color: "text-amber-400" },
    { titulo: "Cerrados", valor: contar("cerrado"), icono: "lock", color: "text-outline" },
  ];

  const abrirModal = () => {
    setError("");
    setNumero("");
    setModal(true);
  };

  const eliminarCaso = async (e, caso) => {
    e.stopPropagation();
    if (!window.confirm(`El caso ${caso.numero_caso} pasará a la papelera por 30 días. ¿Eliminarlo?`)) return;
    try {
      await api.delete(`/casos/${caso.id}`);
      setCasos((prev) => prev.filter((c) => c.id !== caso.id));
      notificar(`Caso ${caso.numero_caso} movido a la papelera.`, { tipo: "info" });
    } catch {
      notificar("No se pudo eliminar el caso.", { tipo: "error" });
    }
  };

  const crearCaso = async (e) => {
    e.preventDefault();
    setError("");
    setGuardando(true);
    try {
      await api.post("/casos", { numero_caso: numero.trim(), especialidad });
      setModal(false);
      await cargar();
    } catch (err) {
      setError(
        err.response?.status === 409
          ? "Ya existe un caso con ese número."
          : "No se pudo crear el caso."
      );
    } finally {
      setGuardando(false);
    }
  };

  return (
    <Layout>
      <div className="flex items-center justify-between mb-space-lg">
        <div>
          <h1 className="font-headline-lg text-headline-lg text-on-surface">Casos</h1>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            Expedientes con evidencia digital bajo cadena de custodia.
          </p>
        </div>
        <button
          onClick={abrirModal}
          className="inline-flex items-center gap-2 px-space-md py-2.5 rounded-lg bg-primary text-on-primary font-headline-sm text-headline-sm hover:bg-primary-container active:scale-[0.99] transition-all shadow-lg shadow-primary/20"
        >
          <span className="material-symbols-outlined text-xl">add</span>
          Nuevo caso
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-gutter mb-space-lg">
        {tarjetas.map((t) => (
          <div key={t.titulo} className="bg-surface-container-low rounded-xl p-space-md flex items-center gap-space-md">
            <div className={`w-12 h-12 rounded-lg bg-surface-container-high flex items-center justify-center ${t.color}`}>
              <span className="material-symbols-outlined text-2xl">{t.icono}</span>
            </div>
            <div>
              <div className="font-headline-xl text-headline-xl text-on-surface leading-none">{t.valor}</div>
              <div className="font-label-ui text-label-ui text-outline uppercase tracking-wider mt-1">{t.titulo}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-surface-container-low rounded-xl p-space-md mb-space-md flex flex-col gap-space-md">
        <div className="relative">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-lg">
            search
          </span>
          <input
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar por número de caso..."
            className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-surface-container-lowest text-on-surface font-body-md text-body-md placeholder:text-outline/60 focus:outline-none focus:ring-1 focus:ring-primary/50"
          />
        </div>
        <div className="flex flex-wrap items-center gap-space-sm">
          <span className="font-label-ui text-label-ui text-outline uppercase tracking-wider mr-1">Especialidad</span>
          <Chip activo={!filtroEsp} onClick={() => setFiltroEsp("")}>Todas</Chip>
          {Object.entries(ESPECIALIDADES).map(([k, v]) => (
            <Chip key={k} activo={filtroEsp === k} onClick={() => setFiltroEsp(k)}>{v.label}</Chip>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-space-sm">
          <span className="font-label-ui text-label-ui text-outline uppercase tracking-wider mr-1">Estado</span>
          <Chip activo={!filtroEst} onClick={() => setFiltroEst("")}>Todos</Chip>
          {Object.entries(ESTADOS).map(([k, v]) => (
            <Chip key={k} activo={filtroEst === k} onClick={() => setFiltroEst(k)}>{v.label}</Chip>
          ))}
        </div>
      </div>

      <div className="bg-surface-container-low rounded-xl overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-surface-container-lowest">
              {["Número de caso", "Especialidad", "Estado", "Creado", "", ""].map((h) => (
                <th key={h} className="px-space-md py-3 font-label-ui text-label-ui text-outline uppercase tracking-wider">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibles.map((c) => {
              const esp = ESPECIALIDADES[c.especialidad];
              const est = ESTADOS[c.estado];
              return (
                <tr
                  key={c.id}
                  onClick={() => navigate(`/casos/${c.id}`)}
                  className="cursor-pointer hover:bg-surface-container transition-colors border-t border-outline-variant/20"
                >
                  <td className="px-space-md py-4 font-label-code-lg text-label-code-lg text-on-surface">
                    {c.numero_caso}
                  </td>
                  <td className="px-space-md py-4">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-high text-secondary font-label-ui text-label-ui uppercase tracking-wider">
                      <span className="material-symbols-outlined text-sm">{esp.icon}</span>
                      {esp.label}
                    </span>
                  </td>
                  <td className="px-space-md py-4">
                    <span className={`inline-flex items-center gap-1.5 font-label-ui text-label-ui uppercase tracking-wider ${est.text}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${est.dot}`}></span>
                      {est.label}
                    </span>
                  </td>
                  <td className="px-space-md py-4 font-body-sm text-body-sm text-on-surface-variant">
                    {new Date(c.creado_en).toLocaleString("es-PE", { dateStyle: "medium", timeStyle: "short" })}
                  </td>
                  <td className="px-space-md py-4 text-right">
                    <button
                      onClick={(e) => eliminarCaso(e, c)}
                      title="Eliminar caso"
                      className="text-outline hover:text-error transition-colors"
                    >
                      <span className="material-symbols-outlined text-xl">delete</span>
                    </button>
                  </td>
                  <td className="px-space-md py-4 text-right text-primary">
                    <span className="material-symbols-outlined">arrow_forward</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {!cargando && visibles.length === 0 && (
          <div className="py-16 flex flex-col items-center text-on-surface-variant">
            <span className="material-symbols-outlined text-5xl text-outline mb-2">folder_off</span>
            <p className="font-body-md text-body-md">No hay casos que coincidan.</p>
          </div>
        )}
      </div>

      {modal && (
        <div
          className="fixed inset-0 z-[60] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setModal(false)}
        >
          <form
            onSubmit={crearCaso}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md bg-surface-container-low rounded-xl p-space-lg shadow-2xl relative"
          >
            <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-transparent via-primary to-transparent opacity-80 rounded-t-xl"></div>
            <h2 className="font-headline-md text-headline-md text-on-surface mb-1">Nuevo caso</h2>
            <p className="font-body-sm text-body-sm text-on-surface-variant mb-space-lg">
              El número de caso debe ser único.
            </p>

            <label className="block font-label-ui text-label-ui text-on-surface-variant uppercase tracking-wider mb-2">
              Número de caso
            </label>
            <input
              value={numero}
              onChange={(e) => setNumero(e.target.value)}
              placeholder="CASO-2026-001"
              required
              autoFocus
              className="w-full px-4 py-3 rounded-lg bg-surface-container-lowest text-on-surface font-label-code-lg text-label-code-lg placeholder:text-outline/60 focus:outline-none focus:ring-1 focus:ring-primary/50 mb-space-md"
            />

            <label className="block font-label-ui text-label-ui text-on-surface-variant uppercase tracking-wider mb-2">
              Especialidad
            </label>
            <div className="grid grid-cols-2 gap-space-sm mb-space-md">
              {Object.entries(ESPECIALIDADES).map(([k, v]) => (
                <button
                  type="button"
                  key={k}
                  onClick={() => setEspecialidad(k)}
                  className={`flex items-center gap-2 px-3 py-3 rounded-lg font-body-md text-body-md transition-colors ${
                    especialidad === k
                      ? "bg-primary/15 text-primary ring-1 ring-primary/40"
                      : "bg-surface-container-lowest text-on-surface-variant hover:bg-surface-container"
                  }`}
                >
                  <span className="material-symbols-outlined text-lg">{v.icon}</span>
                  {v.label}
                </button>
              ))}
            </div>

            {error && <p className="text-error font-body-sm text-body-sm mb-space-md">{error}</p>}

            <div className="flex justify-end gap-space-sm">
              <button
                type="button"
                onClick={() => setModal(false)}
                className="px-space-md py-2.5 rounded-lg text-on-surface-variant hover:bg-surface-container font-body-md text-body-md"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={guardando}
                className="px-space-md py-2.5 rounded-lg bg-primary text-on-primary font-headline-sm text-headline-sm hover:bg-primary-container disabled:opacity-60"
              >
                {guardando ? "Creando..." : "Crear caso"}
              </button>
            </div>
          </form>
        </div>
      )}
    </Layout>
  );
}