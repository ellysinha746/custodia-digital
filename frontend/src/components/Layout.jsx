import { useEffect, useRef, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import api from "../api";
import { useToast } from "./Toast";

function useBusqueda() {
  const [termino, setTermino] = useState("");
  const [resultados, setResultados] = useState(null);
  const [buscando, setBuscando] = useState(false);

  // Los estados "vacío" y "buscando" se ajustan al escribir, no dentro del efecto.
  const cambiarTermino = (valor) => {
    setTermino(valor);
    if (!valor.trim()) {
      setResultados(null);
      setBuscando(false);
    } else {
      setBuscando(true);
    }
  };

  useEffect(() => {
    if (!termino.trim()) return;
    const temporizador = setTimeout(async () => {
      try {
        const { data } = await api.get("/buscar", { params: { q: termino.trim() } });
        setResultados(data);
      } catch {
        setResultados({ casos: [], archivos: [] });
      } finally {
        setBuscando(false);
      }
    }, 250);
    return () => clearTimeout(temporizador);
  }, [termino]);

  return { termino, setTermino: cambiarTermino, resultados, buscando, limpiar: () => cambiarTermino("") };
}

function BuscadorGlobal() {
  const { termino, setTermino, resultados, buscando, limpiar } = useBusqueda();
  const [abierto, setAbierto] = useState(false);
  const navigate = useNavigate();
  const cajaRef = useRef(null);

  useEffect(() => {
    const clicFuera = (e) => {
      if (cajaRef.current && !cajaRef.current.contains(e.target)) setAbierto(false);
    };
    document.addEventListener("mousedown", clicFuera);
    return () => document.removeEventListener("mousedown", clicFuera);
  }, []);

  const irACaso = (casoId) => {
    limpiar();
    setAbierto(false);
    navigate(`/casos/${casoId}`);
  };

  const hayResultados = resultados && (resultados.casos.length > 0 || resultados.archivos.length > 0);
  const sinResultados = resultados && !hayResultados && !buscando;

  return (
    <div className="relative w-full max-w-md" ref={cajaRef}>
      <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-lg pointer-events-none">
        search
      </span>
      <input
        value={termino}
        onChange={(e) => setTermino(e.target.value)}
        onFocus={() => setAbierto(true)}
        placeholder="Buscar caso o archivo..."
        className="w-full pl-10 pr-4 py-2 rounded-lg bg-surface-container text-on-surface font-body-sm text-body-sm placeholder:text-outline/60 focus:outline-none focus:ring-1 focus:ring-primary/50"
      />
      {abierto && termino.trim() && (
        <div className="absolute mt-2 w-full bg-surface-container-high border border-outline-variant/30 rounded-lg shadow-2xl overflow-hidden z-[70] max-h-96 overflow-y-auto">
          {buscando && (
            <p className="px-4 py-3 font-body-sm text-body-sm text-on-surface-variant">Buscando...</p>
          )}
          {sinResultados && (
            <p className="px-4 py-3 font-body-sm text-body-sm text-on-surface-variant">Sin resultados.</p>
          )}
          {resultados?.casos.length > 0 && (
            <div>
              <div className="px-4 pt-3 pb-1 font-label-ui text-label-ui text-outline uppercase tracking-wider">
                Casos
              </div>
              {resultados.casos.map((c) => (
                <button
                  key={c.id}
                  onClick={() => irACaso(c.id)}
                  className="w-full text-left px-4 py-2.5 hover:bg-surface-container flex items-center gap-2.5"
                >
                  <span className="material-symbols-outlined text-lg text-primary">folder_special</span>
                  <span className="font-label-code-sm text-label-code-sm text-on-surface">{c.numero_caso}</span>
                </button>
              ))}
            </div>
          )}
          {resultados?.archivos.length > 0 && (
            <div>
              <div className="px-4 pt-3 pb-1 font-label-ui text-label-ui text-outline uppercase tracking-wider">
                Archivos
              </div>
              {resultados.archivos.map((a) => (
                <button
                  key={a.id}
                  onClick={() => irACaso(a.caso_id)}
                  className="w-full text-left px-4 py-2.5 hover:bg-surface-container flex items-center gap-2.5"
                >
                  <span className="material-symbols-outlined text-lg text-secondary">description</span>
                  <div className="flex flex-col">
                    <span className="font-body-sm text-body-sm text-on-surface">{a.nombre_original}</span>
                    <span className="font-label-code-sm text-label-code-sm text-outline">
                      Caso {a.caso_numero}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Layout({ children }) {
  const [usuario, setUsuario] = useState(null);
  const [pendientes, setPendientes] = useState(0);
  const ultimoConteo = useRef(null);
  const navigate = useNavigate();
  const { notificar, pedirPermisoNotificacion } = useToast();

  // Sprint 4: contador de alertas pendientes; avisa cuando aparece una nueva.
  useEffect(() => {
    const revisar = async () => {
      try {
        const { data } = await api.get("/alertas/resumen");
        if (ultimoConteo.current !== null && data.pendientes > ultimoConteo.current) {
          notificar("Se detectó una nueva alerta de integridad.", {
            tipo: "error",
            sistemaOperativo: true,
            titulo: "Alerta de integridad",
          });
        }
        ultimoConteo.current = data.pendientes;
        setPendientes(data.pendientes);
      } catch {
        // sin sesión o backend caído: el contador simplemente no se actualiza
      }
    };
    revisar();
    const intervalo = setInterval(revisar, 30000);
    return () => clearInterval(intervalo);
  }, [notificar]);

  useEffect(() => {
    pedirPermisoNotificacion();
    api
      .get("/auth/me")
      .then(({ data }) => setUsuario(data))
      .catch((err) => {
        if (err.response?.status === 401) {
          localStorage.clear();
          navigate("/");
        }
      });
  }, [navigate, pedirPermisoNotificacion]);

  const cerrarSesion = () => {
    localStorage.clear();
    navigate("/");
  };

  const iniciales = usuario
    ? usuario.nombre.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase()
    : "··";

  const navItems = [
    { to: "/casos", icono: "folder_special", texto: "Casos" },
    { to: "/auditoria", icono: "history_edu", texto: "Auditoría" },
        { to: "/alertas", icono: "gpp_maybe", texto: "Alertas", contador: pendientes },
    { to: "/papelera", icono: "delete_sweep", texto: "Papelera" },
  ];

  return (
    <div className="min-h-screen bg-surface">
      <header className="fixed top-0 left-0 right-0 z-50 bg-surface-container-lowest/90 backdrop-blur-md shadow-[0_1px_8px_rgba(0,0,0,0.45)]">
        <div className="h-16 w-full px-gutter flex items-center justify-between gap-space-lg">
          <div className="flex items-center gap-space-md shrink-0">
            <div className="w-9 h-9 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
              <span className="material-symbols-outlined">shield_lock</span>
            </div>
            <div className="hidden md:flex flex-col">
              <span className="font-headline-sm text-headline-sm tracking-tight text-on-surface">CustodiaDigital</span>
              <span className="font-label-code-sm text-label-code-sm text-outline uppercase tracking-wider">
                Cadena de Custodia Forense
              </span>
            </div>
          </div>

          <BuscadorGlobal />

          <div className="flex items-center gap-space-sm px-space-md py-space-xs rounded-full bg-surface-container border border-outline-variant/40 shrink-0">
            <div className="relative w-8 h-8 rounded-full bg-primary/15 text-primary ring-1 ring-primary/30 flex items-center justify-center font-label-ui text-label-ui">
              {iniciales}
              <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-tertiary ring-2 ring-surface-container-lowest"></span>
            </div>
            <div className="hidden lg:flex flex-col pr-space-xs">
              <span className="font-body-sm text-body-sm font-semibold text-on-surface">
                {usuario ? usuario.nombre : "Perito"}
              </span>
              <span className="font-label-code-sm text-label-code-sm text-on-surface-variant">
                {usuario ? `Perito en ${usuario.especialidad}` : "Cargando..."}
              </span>
            </div>
          </div>
        </div>
      </header>

      <aside className="fixed left-0 top-16 bottom-0 w-64 bg-surface-container-lowest z-40 flex flex-col justify-between py-space-lg border-r border-outline-variant/30">
        <div className="flex flex-col gap-space-lg">
          <div className="px-space-lg">
            <span className="font-label-ui text-label-ui text-outline uppercase tracking-widest block">
              Consola Pericial
            </span>
          </div>
          <nav className="flex flex-col px-space-sm gap-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-space-md py-2.5 rounded-r-lg transition-colors font-body-md text-body-md ${
                    isActive
                      ? "bg-surface-container-high text-primary font-semibold border-l-2 border-primary"
                      : "text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
                  }`
                }
              >
                <span className="material-symbols-outlined">{item.icono}</span>
                <span>{item.texto}</span>
                                {item.contador > 0 && (
                  <span className="ml-auto min-w-5 h-5 px-1.5 rounded-full bg-error text-on-error font-label-ui text-label-ui flex items-center justify-center">
                    {item.contador}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="px-space-md">
          <button
            onClick={cerrarSesion}
            className="w-full flex items-center gap-3 px-space-md py-2.5 rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-error transition-colors font-body-md text-body-md"
          >
            <span className="material-symbols-outlined">logout</span>
            <span>Cerrar sesión</span>
          </button>
        </div>
      </aside>

      <main className="pl-64 pt-16 min-h-screen">
        <div className="px-gutter py-space-lg">{children}</div>
      </main>
    </div>
  );
}
