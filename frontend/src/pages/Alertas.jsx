import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import Layout from "../components/Layout";
import { useToast } from "../components/Toast";

const FILTROS = [
  { valor: "pendiente", texto: "Pendientes" },
  { valor: "atendida", texto: "Atendidas" },
  { valor: "", texto: "Todas" },
];

const UBICACION = {
  original: "Original",
  copia: "Copia de trabajo",
  ambos: "Original y copia",
  dispositivo: "Dispositivo",
};

function hashCorto(h) {
  if (!h) return "— (no existe)";
  return `${h.slice(0, 12)}…${h.slice(-6)}`;
}

export default function Alertas() {
  const [alertas, setAlertas] = useState([]);
  const [filtro, setFiltro] = useState("pendiente");
  const [cargando, setCargando] = useState(true);
  const [esAdmin, setEsAdmin] = useState(false);
  const [escaneando, setEscaneando] = useState(false);
  const navigate = useNavigate();
  const { notificar } = useToast();

  // Subir "recarga" vuelve a pedir la lista (después de escanear o atender).
  const [recarga, setRecarga] = useState(0);
  const recargar = () => setRecarga((n) => n + 1);

  useEffect(() => {
    let activo = true;
    api
      .get("/alertas", { params: filtro ? { estado: filtro } : {} })
      .then(({ data }) => activo && setAlertas(data))
      .catch((err) => {
        if (err.response?.status === 401) {
          localStorage.clear();
          navigate("/");
        }
      })
      .finally(() => activo && setCargando(false));
    return () => {
      activo = false;
    };
  }, [filtro, recarga, navigate]);

  useEffect(() => {
    api.get("/auth/me").then(({ data }) => setEsAdmin(data.rol === "admin")).catch(() => {});
  }, []);

  const escanear = async () => {
    setEscaneando(true);
    try {
      const { data } = await api.post("/alertas/escanear");
      notificar(
        `Escaneo terminado: ${data.archivos_revisados} archivo(s) revisados, ${data.alertas_nuevas} alerta(s) nuevas.`,
        { tipo: data.alertas_nuevas > 0 ? "error" : "success" }
      );
      recargar();
    } catch (err) {
      notificar(err.response?.data?.detail || "No se pudo escanear.", { tipo: "error" });
    } finally {
      setEscaneando(false);
    }
  };

  const atender = async (alerta) => {
    const nota = window.prompt("Nota de la investigación (opcional):", "");
    if (nota === null) return;
    try {
      await api.patch(`/alertas/${alerta.id}/atender`, { nota: nota || null });
      notificar("Alerta marcada como atendida.", { tipo: "success" });
      recargar();
    } catch (err) {
      notificar(err.response?.data?.detail || "No se pudo atender la alerta.", { tipo: "error" });
    }
  };

  return (
    <Layout>
      <div className="mb-space-lg flex items-end justify-between gap-space-md">
        <div>
          <h1 className="font-headline-lg text-headline-lg text-on-surface">Alertas de integridad</h1>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            Cambios de hash o del dispositivo de origen detectados sin un registro de custodia que los respalde.
          </p>
        </div>
        {esAdmin && (
          <button
            onClick={escanear}
            disabled={escaneando}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui hover:opacity-90 disabled:opacity-50"
          >
            <span className="material-symbols-outlined text-base">radar</span>
            {escaneando ? "Escaneando..." : "Escanear ahora"}
          </button>
        )}
      </div>

      <div className="flex gap-2 mb-space-md">
        {FILTROS.map((f) => (
          <button
            key={f.valor}
            onClick={() => {
              if (f.valor === filtro) return;
              setCargando(true);
              setFiltro(f.valor);
            }}
            className={`px-3 py-1.5 rounded-lg font-label-ui text-label-ui ${
              filtro === f.valor
                ? "bg-surface-container-high text-primary"
                : "text-on-surface-variant hover:bg-surface-container"
            }`}
          >
            {f.texto}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-space-sm">
        {alertas.map((a) => (
          <div
            key={a.id}
            className={`bg-surface-container-low rounded-xl p-space-md border-l-4 ${
              a.atendida_en ? "border-outline" : "border-error"
            }`}
          >
            <div className="flex items-start justify-between gap-space-md">
              <div className="flex items-start gap-3">
                <span className={`material-symbols-outlined text-2xl ${a.atendida_en ? "text-outline" : "text-error"}`}>
                  {a.atendida_en ? "task_alt" : "gpp_bad"}
                </span>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <button
                      onClick={() => navigate(`/casos/${a.caso_id}`)}
                      className="font-label-code-lg text-label-code-lg text-primary hover:underline"
                    >
                      {a.caso_numero}
                    </button>
                    <span className="font-body-sm text-body-sm text-on-surface">· {a.archivo_nombre}</span>
                    <span className="px-2 py-0.5 rounded bg-error/10 text-error font-label-ui text-label-ui uppercase tracking-wider">
                      {UBICACION[a.ubicacion] || a.ubicacion}
                    </span>
                  </div>
                  <p className="font-body-sm text-body-sm text-on-surface-variant mt-1">{a.detalle}</p>
                  {a.tipo === "hash_sin_respaldo" && (
                    <div className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 font-label-code-sm text-label-code-sm">
                      <span className="text-outline">Esperado</span>
                      <span className="text-on-surface-variant">{hashCorto(a.hash_esperado)}</span>
                      <span className="text-outline">Encontrado</span>
                      <span className="text-error">{hashCorto(a.hash_encontrado)}</span>
                    </div>
                  )}
                  <div className="mt-2 flex items-center gap-3 flex-wrap font-label-code-sm text-label-code-sm text-outline">
                    <span>{new Date(a.creada_en).toLocaleString("es-PE")}</span>
                    <span>· {a.origen === "verificacion_manual" ? "Verificación manual" : "Escaneo automático"}</span>
                    <span className="inline-flex items-center gap-1">
                      · <span className="material-symbols-outlined text-sm">{a.correo_enviado ? "mark_email_read" : "unsubscribe"}</span>
                      {a.correo_enviado ? "Correo enviado" : "Correo no enviado"}
                    </span>
                  </div>
                  {a.atendida_en && (
                    <p className="mt-2 font-body-sm text-body-sm text-on-surface-variant">
                      Atendida por <strong>{a.atendida_por_nombre}</strong> el{" "}
                      {new Date(a.atendida_en).toLocaleString("es-PE")}
                      {a.nota_atencion ? ` — "${a.nota_atencion}"` : ""}
                    </p>
                  )}
                </div>
              </div>
              {esAdmin && !a.atendida_en && (
                <button
                  onClick={() => atender(a)}
                  className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-high text-primary font-label-ui text-label-ui hover:bg-surface-container"
                >
                  <span className="material-symbols-outlined text-base">done</span>
                  Marcar atendida
                </button>
              )}
            </div>
          </div>
        ))}

        {!cargando && alertas.length === 0 && (
          <div className="py-16 flex flex-col items-center text-on-surface-variant bg-surface-container-low rounded-xl">
            <span className="material-symbols-outlined text-5xl text-outline mb-2">verified_user</span>
            <p className="font-body-md text-body-md">No hay alertas en esta vista.</p>
          </div>
        )}
      </div>
    </Layout>
  );
}