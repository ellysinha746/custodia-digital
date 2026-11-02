import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api from "../api";
import Layout from "../components/Layout";
import { useToast } from "../components/Toast";
import FichaDispositivo, { CamposFicha } from "../components/FichaDispositivo";
import VersionesObservadas from "../components/VersionesObservadas";

const ESPECIALIDADES = {
  audio: { label: "Audio", icon: "graphic_eq" },
  video: { label: "Video", icon: "videocam" },
  informatica: { label: "Informática", icon: "computer" },
  telefonia: { label: "Telefonía", icon: "smartphone" },
};

const ESTADOS_CASO = {
  abierto: { label: "Abierto", text: "text-tertiary", dot: "bg-tertiary", siguiente: "en_proceso" },
  en_proceso: { label: "En proceso", text: "text-amber-400", dot: "bg-amber-400 animate-pulse", siguiente: "cerrado" },
  cerrado: { label: "Cerrado", text: "text-outline", dot: "bg-outline", siguiente: null },
};

const CAMPOS_METADATOS = {
  audio: [
    { clave: "duracion_seg", etiqueta: "Duración (s)" },
    { clave: "tasa_muestreo_hz", etiqueta: "Tasa de muestreo (Hz)" },
  ],
  video: [
    { clave: "resolucion", etiqueta: "Resolución" },
    { clave: "codec", etiqueta: "Códec" },
    { clave: "duracion_seg", etiqueta: "Duración (s)" },
  ],
  informatica: [
    { clave: "sistema_archivos", etiqueta: "Sistema de archivos" },
    { clave: "hash_disco", etiqueta: "Hash de disco" },
  ],
  telefonia: [
    { clave: "imei", etiqueta: "IMEI" },
    { clave: "operador", etiqueta: "Operador" },
  ],
};

const ACCION_INFO = {
  subida: { icono: "upload_file", label: "Subida", color: "text-secondary" },
  acceso: { icono: "visibility", label: "Acceso", color: "text-outline" },
  descarga: { icono: "download", label: "Descarga", color: "text-primary" },
  verificacion: { icono: "verified", label: "Verificación", color: "text-tertiary" },
};

function badgeProcesamiento(estado) {
  if (estado === "listo") {
    return <span className="inline-flex items-center gap-1 text-tertiary font-label-ui text-label-ui uppercase tracking-wider"><span className="w-1.5 h-1.5 rounded-full bg-tertiary"/>Listo</span>;
  }
  return <span className="inline-flex items-center gap-1 text-amber-400 font-label-ui text-label-ui uppercase tracking-wider"><span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"/>Procesando</span>;
}

function FilaArchivo({ archivo, caso, onCambio }) {
  const [expandido, setExpandido] = useState(false);
  const [historial, setHistorial] = useState(null);
  const [verificando, setVerificando] = useState(false);
  const [resultadoVerif, setResultadoVerif] = useState(null);
  const [editandoMeta, setEditandoMeta] = useState(false);
  const [metaForm, setMetaForm] = useState({});
  const [guardandoMeta, setGuardandoMeta] = useState(false);
  const { notificar } = useToast();

  const campos = CAMPOS_METADATOS[caso.especialidad] || [];
  const puedeEscribir = caso.estado !== "cerrado";

  const cargarHistorial = useCallback(async () => {
    try {
      const { data } = await api.get(`/archivos/${archivo.id}/historial`);
      setHistorial(data);
    } catch {
      setHistorial([]);
    }
  }, [archivo.id]);

  const alternarExpandido = () => {
    const nuevo = !expandido;
    setExpandido(nuevo);
    if (nuevo && !historial) cargarHistorial();
  };

  const verificar = async () => {
    setVerificando(true);
    try {
      const { data } = await api.post(`/archivos/${archivo.id}/verificar`);
      setResultadoVerif(data.resultado);
      notificar(
        data.resultado === "integro"
          ? `${archivo.nombre_original}: el archivo sigue íntegro.`
          : `${archivo.nombre_original}: ¡el hash no coincide! Se registró una alerta de integridad.`,
        { tipo: data.resultado === "integro" ? "success" : "error" }
      );
      cargarHistorial();
    } catch (err) {
      notificar(err.response?.data?.detail || "No se pudo verificar el archivo.", { tipo: "error" });
    } finally {
      setVerificando(false);
    }
  };

  // Sprint 4 (historia 14): se elige descargar la copia de trabajo o el original.
  const descargar = async (version = "copia") => {
    try {
      const { data } = await api.get(`/archivos/${archivo.id}/descargar`, {
        params: { version },
        responseType: "blob",
      });
      const url = URL.createObjectURL(data);
      const a = document.createElement("a");
      a.href = url;
      a.download = version === "original" ? `ORIGINAL_${archivo.nombre_original}` : archivo.nombre_original;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      cargarHistorial();
    } catch (err) {
      let detalle = "No se pudo descargar el archivo.";
      try {
        detalle = JSON.parse(await err.response.data.text()).detail || detalle;
      } catch {
        // la respuesta no traía un mensaje legible
      }
      notificar(detalle, { tipo: "error" });
    }
  };

  const abrirEdicionMeta = () => {
    const base = {};
    campos.forEach((c) => {
      base[c.clave] = archivo.metadatos?.[c.clave] ?? "";
    });
    setMetaForm(base);
    setEditandoMeta(true);
  };

  const guardarMeta = async (e) => {
    e.preventDefault();
    setGuardandoMeta(true);
    try {
      await api.patch(`/archivos/${archivo.id}/metadatos`, { metadatos: metaForm });
      setEditandoMeta(false);
      notificar("Metadatos actualizados.", { tipo: "success" });
      onCambio();
    } catch {
      notificar("No se pudieron guardar los metadatos.", { tipo: "error" });
    } finally {
      setGuardandoMeta(false);
    }
  };

  return (
    <div className="border-t border-outline-variant/20">
      <button
        onClick={alternarExpandido}
        className="w-full flex items-center gap-space-md px-space-md py-3.5 text-left hover:bg-surface-container transition-colors"
      >
        <span className="material-symbols-outlined text-outline text-xl">
          {expandido ? "expand_less" : "expand_more"}
        </span>
        <span className="material-symbols-outlined text-primary">description</span>
        <span className="flex-1 font-body-md text-body-md text-on-surface truncate">{archivo.nombre_original}</span>
        {badgeProcesamiento(archivo.estado_procesamiento)}
        <span className="font-label-code-sm text-label-code-sm text-outline hidden sm:block">
          {archivo.hash_actual ? `${archivo.hash_actual.slice(0, 10)}…` : "—"}
        </span>
      </button>

      {expandido && (
        <div className="px-space-md pb-space-md pl-12 flex flex-col gap-space-md">
          {archivo.estado_procesamiento !== "listo" ? (
            <p className="font-body-sm text-body-sm text-on-surface-variant flex items-center gap-2">
              <span className="material-symbols-outlined text-lg animate-spin">progress_activity</span>
              Calculando el hash en segundo plano. Puedes seguir trabajando; te avisamos al terminar.
            </p>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-space-sm">
                <button
                  onClick={verificar}
                  disabled={verificando}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface font-label-ui text-label-ui hover:bg-surface-container disabled:opacity-60"
                >
                  <span className="material-symbols-outlined text-base">enhanced_encryption</span>
                  {verificando ? "Verificando..." : "Verificar integridad"}
                </button>
                <button
                  onClick={() => descargar("copia")}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface font-label-ui text-label-ui hover:bg-surface-container"
                >
                  <span className="material-symbols-outlined text-base">download</span>
                  Descargar copia
                </button>
                <button
                  onClick={() => descargar("original")}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface font-label-ui text-label-ui hover:bg-surface-container"
                >
                  <span className="material-symbols-outlined text-base">lock_open</span>
                  Descargar original
                </button>
                {resultadoVerif && (
                  <span
                    className={`font-label-ui text-label-ui uppercase tracking-wider ${
                      resultadoVerif === "integro" ? "text-tertiary" : "text-error"
                    }`}
                  >
                    {resultadoVerif === "integro" ? "Íntegro" : "Alterado"}
                  </span>
                )}
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-label-ui text-label-ui text-outline uppercase tracking-wider">
                    Metadatos ({ESPECIALIDADES[caso.especialidad].label})
                  </span>
                  {puedeEscribir && !editandoMeta && (
                    <button
                      onClick={abrirEdicionMeta}
                      className="font-label-ui text-label-ui text-primary hover:underline"
                    >
                      Editar
                    </button>
                  )}
                </div>
                {editandoMeta ? (
                  <form onSubmit={guardarMeta} className="grid sm:grid-cols-2 gap-space-sm bg-surface-container-high rounded-lg p-space-sm">
                    {campos.map((c) => (
                      <label key={c.clave} className="flex flex-col gap-1">
                        <span className="font-label-code-sm text-label-code-sm text-outline">{c.etiqueta}</span>
                        <input
                          value={metaForm[c.clave] ?? ""}
                          onChange={(e) => setMetaForm({ ...metaForm, [c.clave]: e.target.value })}
                          className="px-2.5 py-1.5 rounded-md bg-surface-container-lowest text-on-surface font-body-sm text-body-sm focus:outline-none focus:ring-1 focus:ring-primary/50"
                        />
                      </label>
                    ))}
                    <div className="sm:col-span-2 flex justify-end gap-space-sm mt-1">
                      <button
                        type="button"
                        onClick={() => setEditandoMeta(false)}
                        className="px-3 py-1.5 rounded-lg font-label-ui text-label-ui text-on-surface-variant hover:bg-surface-container"
                      >
                        Cancelar
                      </button>
                      <button
                        type="submit"
                        disabled={guardandoMeta}
                        className="px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui disabled:opacity-60"
                      >
                        {guardandoMeta ? "Guardando..." : "Guardar"}
                      </button>
                    </div>
                  </form>
                ) : campos.some((c) => archivo.metadatos?.[c.clave]) ? (
                  <dl className="grid sm:grid-cols-2 gap-x-space-md gap-y-1">
                    {campos.map((c) => (
                      <div key={c.clave} className="flex justify-between sm:justify-start sm:gap-2">
                        <dt className="font-body-sm text-body-sm text-on-surface-variant">{c.etiqueta}:</dt>
                        <dd className="font-label-code-sm text-label-code-sm text-on-surface">
                          {archivo.metadatos?.[c.clave] || "—"}
                        </dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <p className="font-body-sm text-body-sm text-outline">Sin metadatos registrados.</p>
                )}
              </div>

              <FichaDispositivo
                archivo={archivo}
                puedeEscribir={puedeEscribir}
                onCambio={onCambio}
                onHistorial={cargarHistorial}
              />

              <VersionesObservadas
                archivo={archivo}
                puedeEscribir={puedeEscribir}
                onHistorial={cargarHistorial}
              />
            </>
          )}

          <div>
            <span className="font-label-ui text-label-ui text-outline uppercase tracking-wider block mb-1.5">
              Historial de custodia
            </span>
            {!historial ? (
              <p className="font-body-sm text-body-sm text-outline">Cargando...</p>
            ) : historial.length === 0 ? (
              <p className="font-body-sm text-body-sm text-outline">Sin eventos todavía.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {historial.map((log) => {
                  const info = ACCION_INFO[log.accion];
                  return (
                    <li key={log.id} className="flex items-center gap-2.5 text-body-sm font-body-sm">
                      <span className={`material-symbols-outlined text-lg ${info.color}`}>{info.icono}</span>
                      <span className="text-on-surface">{info.label}</span>
                      {log.resultado && (
                        <span
                          className={`font-label-code-sm text-label-code-sm px-1.5 py-0.5 rounded ${
                            ["alterado", "dispositivo_distinto"].includes(log.resultado)
                              ? "bg-error/15 text-error"
                              : "bg-surface-container-high text-on-surface-variant"
                          }`}
                        >
                          {log.resultado}
                        </span>
                      )}
                      <span className="text-outline">·</span>
                      <span className="text-on-surface-variant">{log.usuario_nombre}</span>
                      <span className="text-outline">·</span>
                      <span className="text-outline font-label-code-sm text-label-code-sm">
                        {new Date(log.fecha).toLocaleString("es-PE", { dateStyle: "medium", timeStyle: "short" })}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function CasoDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { notificar } = useToast();

  const [caso, setCaso] = useState(null);
  const [archivos, setArchivos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [archivoSel, setArchivoSel] = useState(null);
  const [progreso, setProgreso] = useState(0);
  const [subiendo, setSubiendo] = useState(false);
  const [error, setError] = useState("");
  const [cambiandoEstado, setCambiandoEstado] = useState(false);
  const [ficha, setFicha] = useState({ imei: "", modelo: "", mac: "", sistema_operativo: "" });
  const [mostrarFicha, setMostrarFicha] = useState(false);
  const notificadosRef = useRef(new Set());

  const cargarTodo = useCallback(async () => {
    try {
      const [{ data: datoCaso }, { data: datoArchivos }] = await Promise.all([
        api.get(`/casos/${id}`),
        api.get(`/casos/${id}/archivos`),
      ]);
      setCaso(datoCaso);
      setArchivos(datoArchivos);
    } catch (err) {
      if (err.response?.status === 401) {
        localStorage.clear();
        navigate("/");
        return;
      }
      navigate("/casos");
    } finally {
      setCargando(false);
    }
  }, [id, navigate]);

  useEffect(() => {
    // Carga inicial: el setState ocurre después del await, no hay render en cascada.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    cargarTodo();
  }, [cargarTodo]);

  // Sprint 2: mientras haya archivos "procesando", se consulta su estado
  // cada 2s y se notifica apenas terminan (sin bloquear la pantalla).
  useEffect(() => {
    const hayPendientes = archivos.some((a) => a.estado_procesamiento !== "listo");
    if (!hayPendientes) return;

    const intervalo = setInterval(async () => {
      const pendientes = archivos.filter((a) => a.estado_procesamiento !== "listo");
      const actualizados = await Promise.all(
        pendientes.map((a) => api.get(`/archivos/${a.id}`).then((r) => r.data).catch(() => a))
      );
      setArchivos((prev) =>
        prev.map((a) => actualizados.find((u) => u.id === a.id) || a)
      );
      actualizados.forEach((a) => {
        if (a.estado_procesamiento === "listo" && !notificadosRef.current.has(a.id)) {
          notificadosRef.current.add(a.id);
          notificar(`${a.nombre_original} ya terminó de procesarse.`, {
            tipo: "success",
            sistemaOperativo: true,
            titulo: "Procesamiento completado",
          });
        }
      });
    }, 2000);

    return () => clearInterval(intervalo);
  }, [archivos, notificar]);

  const subir = async (e) => {
    e.preventDefault();
    if (!archivoSel) return;
    setError("");
    setProgreso(0);
    setSubiendo(true);

    const formData = new FormData();
    formData.append("archivo", archivoSel);
    // Sprint 4 (historia 13): ficha opcional del dispositivo de origen
    Object.entries(ficha).forEach(([clave, valor]) => {
      if (valor.trim()) formData.append(clave, valor.trim());
    });

    try {
      const { data } = await api.post(`/casos/${id}/archivos`, formData, {
        onUploadProgress: (ev) => {
          if (ev.total) setProgreso(Math.round((ev.loaded * 100) / ev.total));
        },
      });
      setArchivos((prev) => [data, ...prev]);
      setArchivoSel(null);
      e.target.reset();
      setFicha({ imei: "", modelo: "", mac: "", sistema_operativo: "" });
      setMostrarFicha(false);
      if (data.estado_procesamiento === "listo") {
        notificar(`${data.nombre_original} se subió y quedó en custodia.`, { tipo: "success" });
      }
    } catch (err) {
      if (err.response?.status === 401) {
        localStorage.clear();
        navigate("/");
        return;
      }
      setError(
        err.response?.status === 409
          ? "El caso está cerrado: no admite más archivos."
          : typeof err.response?.data?.detail === "string"
          ? err.response.data.detail
          : "No se pudo subir el archivo."
      );
    } finally {
      setSubiendo(false);
    }
  };

  const avanzarEstado = async () => {
    const siguiente = ESTADOS_CASO[caso.estado].siguiente;
    if (!siguiente) return;
    if (siguiente === "cerrado" && !window.confirm("Un caso cerrado ya no admite más cambios. ¿Cerrar el caso?")) {
      return;
    }
    setCambiandoEstado(true);
    try {
      const { data } = await api.patch(`/casos/${id}`, { estado: siguiente });
      setCaso(data);
      notificar(`Caso ahora en estado "${ESTADOS_CASO[data.estado].label}".`, { tipo: "success" });
    } catch {
      notificar("No se pudo cambiar el estado del caso.", { tipo: "error" });
    } finally {
      setCambiandoEstado(false);
    }
  };

  const eliminarCaso = async () => {
    if (!window.confirm("El caso pasará a la papelera por 30 días. ¿Eliminarlo?")) return;
    try {
      await api.delete(`/casos/${id}`);
      notificar("Caso movido a la papelera.", { tipo: "info" });
      navigate("/casos");
    } catch {
      notificar("No se pudo eliminar el caso.", { tipo: "error" });
    }
  };

  if (cargando || !caso) {
    return (
      <Layout>
        <p className="font-body-md text-body-md text-on-surface-variant">Cargando caso...</p>
      </Layout>
    );
  }

  const est = ESTADOS_CASO[caso.estado];
  const esp = ESPECIALIDADES[caso.especialidad];
  const cerrado = caso.estado === "cerrado";

  return (
    <Layout>
      <button
        onClick={() => navigate("/casos")}
        className="flex items-center gap-1.5 font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface mb-space-md"
      >
        <span className="material-symbols-outlined text-lg">arrow_back</span>
        Volver a casos
      </button>

      <div className="flex items-start justify-between gap-space-md mb-space-lg flex-wrap">
        <div>
          <div className="flex items-center gap-space-sm mb-1">
            <h1 className="font-headline-lg text-headline-lg text-on-surface">{caso.numero_caso}</h1>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-high text-secondary font-label-ui text-label-ui uppercase tracking-wider">
              <span className="material-symbols-outlined text-sm">{esp.icon}</span>
              {esp.label}
            </span>
          </div>
          <span className={`inline-flex items-center gap-1.5 font-label-ui text-label-ui uppercase tracking-wider ${est.text}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${est.dot}`}></span>
            {est.label}
          </span>
        </div>

        <div className="flex gap-space-sm">
          {est.siguiente && (
            <button
              onClick={avanzarEstado}
              disabled={cambiandoEstado}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-surface-container-high text-on-surface font-label-ui text-label-ui hover:bg-surface-container disabled:opacity-60"
            >
              <span className="material-symbols-outlined text-base">
                {est.siguiente === "cerrado" ? "lock" : "pending_actions"}
              </span>
              {est.siguiente === "cerrado" ? "Cerrar caso" : "Pasar a en proceso"}
            </button>
          )}
          <button
            onClick={eliminarCaso}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-error hover:bg-error/10 font-label-ui text-label-ui"
          >
            <span className="material-symbols-outlined text-base">delete</span>
            Eliminar
          </button>
        </div>
      </div>

      {cerrado && (
        <div className="flex items-center gap-2 bg-surface-container-high border border-outline-variant/30 rounded-lg px-space-md py-3 mb-space-md">
          <span className="material-symbols-outlined text-outline">lock</span>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            Este caso está cerrado. No se pueden subir archivos ni editar metadatos.
          </p>
        </div>
      )}

      {!cerrado && (
        <div className="bg-surface-container-low rounded-xl p-space-md mb-space-md">
          <h2 className="font-headline-sm text-headline-sm text-on-surface mb-space-sm">Subir evidencia</h2>
          <form onSubmit={subir} className="flex flex-col sm:flex-row gap-space-sm sm:items-center">
            <input
              type="file"
              onChange={(e) => setArchivoSel(e.target.files[0])}
              required
              className="flex-1 font-body-sm text-body-sm text-on-surface-variant file:mr-3 file:px-3 file:py-2 file:rounded-lg file:border-0 file:bg-surface-container-high file:text-on-surface file:font-label-ui file:text-label-ui"
            />
            <button
              type="submit"
              disabled={subiendo || !archivoSel}
              className="px-space-md py-2.5 rounded-lg bg-primary text-on-primary font-headline-sm text-headline-sm hover:bg-primary-container disabled:opacity-60 whitespace-nowrap"
            >
              {subiendo ? "Subiendo..." : "Subir archivo"}
            </button>
          </form>
          <button
            type="button"
            onClick={() => setMostrarFicha(!mostrarFicha)}
            className="mt-space-sm inline-flex items-center gap-1 font-label-ui text-label-ui text-primary hover:underline"
          >
            <span className="material-symbols-outlined text-base">{mostrarFicha ? "expand_less" : "smartphone"}</span>
            {mostrarFicha ? "Ocultar ficha del dispositivo" : "Agregar ficha del dispositivo (opcional)"}
          </button>
          {mostrarFicha && (
            <div className="mt-space-sm">
              <CamposFicha valor={ficha} onChange={setFicha} />
            </div>
          )}
          {subiendo && (
            <div className="mt-space-sm">
              <div className="h-1.5 w-full bg-surface-container-high rounded-full overflow-hidden">
                <div className="h-full bg-primary transition-all" style={{ width: `${progreso}%` }} />
              </div>
            </div>
          )}
          {error && <p className="text-error font-body-sm text-body-sm mt-space-sm">{error}</p>}
        </div>
      )}

      <div className="bg-surface-container-low rounded-xl overflow-hidden">
        <div className="px-space-md py-3 flex items-center justify-between border-b border-outline-variant/20">
          <h2 className="font-headline-sm text-headline-sm text-on-surface">Archivos del caso</h2>
          <span className="font-label-code-sm text-label-code-sm text-outline">{archivos.length} archivo(s)</span>
        </div>
        {archivos.length === 0 ? (
          <div className="py-16 flex flex-col items-center text-on-surface-variant">
            <span className="material-symbols-outlined text-5xl text-outline mb-2">folder_off</span>
            <p className="font-body-md text-body-md">Aún no se sube evidencia a este caso.</p>
          </div>
        ) : (
          archivos.map((a) => (
            <FilaArchivo key={a.id} archivo={a} caso={caso} onCambio={cargarTodo} />
          ))
        )}
      </div>
    </Layout>
  );
}