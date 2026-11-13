import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import { limpiarSesion } from "../sesion";
import Layout from "../components/Layout";
import { useToast } from "../components/Toast";
import { ETIQUETAS_ROL, useUsuario } from "../permisos";

// Sprint 5 (historia 19.1): gestión de usuarios y roles (solo jefe de laboratorio).

const ESPECIALIDADES = {
  audio: "Audio",
  video: "Video",
  informatica: "Informática",
  telefonia: "Telefonía",
};

const DESCRIPCION_ROL = {
  admin: "Gestiona usuarios, ve todo, atiende alertas y el dashboard.",
  perito: "Crea casos, sube evidencia, verifica y registra fichas en sus casos.",
  perito_parte: "Solo ve los casos donde lo designen y formula observaciones (CPP art. 177).",
  fiscal: "Ve todos los casos y dirige el trámite pericial: designa, corre traslado, subroga y concluye.",
};

const VACIO = {
  nombre: "", email: "", password: "", especialidad: "telefonia", rol: "perito",
  institucion: "", registro_profesional: "", telefono: "",
};
const ES_PERITO_ROL = (rol) => rol === "perito" || rol === "perito_parte";
// Sprint 6 (historia 24): roles que no entran sin verificación en dos pasos (TOTP_ROLES_OBLIGATORIO).
const ROLES_CON_2FA = ["admin", "fiscal"];

// Sprint 6 (historia 25): solicitud de cuenta pendiente de aprobación.
function SolicitudPendiente({ u, onListo }) {
  const [rol, setRol] = useState(u.rol);
  const [especialidad, setEspecialidad] = useState(u.especialidad || "informatica");
  const [rechazando, setRechazando] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const { notificar } = useToast();

  const enviar = async (ruta, cuerpo, mensaje) => {
    setOcupado(true);
    try {
      await api.post(`/usuarios/${u.id}/${ruta}`, cuerpo);
      notificar(mensaje, { tipo: "success" });
      onListo();
    } catch (err) {
      notificar(err.response?.data?.detail || "No se pudo procesar la solicitud.", { tipo: "error" });
    } finally {
      setOcupado(false);
    }
  };

  return (
    <div className="border-t border-outline-variant/20 px-space-md py-3 flex flex-col gap-space-sm">
      <div className="flex flex-wrap items-start justify-between gap-space-sm">
        <div className="min-w-0">
          <div className="font-body-sm text-body-sm text-on-surface font-semibold">{u.nombre}</div>
          <div className="font-label-code-sm text-label-code-sm text-outline">{u.email}</div>
          <div className="font-body-sm text-body-sm text-on-surface-variant">
            Pide ser {ETIQUETAS_ROL[u.rol]} de {ESPECIALIDADES[u.especialidad] || "—"}
            {[u.institucion, u.registro_profesional, u.telefono].filter(Boolean).length > 0 &&
              ` · ${[u.institucion, u.registro_profesional, u.telefono].filter(Boolean).join(" · ")}`}
          </div>
          {u.creado_en && (
            <div className="font-label-code-sm text-label-code-sm text-outline">
              Solicitada el {new Date(u.creado_en).toLocaleString("es-PE")}
            </div>
          )}
        </div>
        {!rechazando && (
          <div className="flex flex-wrap items-center gap-space-sm">
            <select value={rol} onChange={(e) => setRol(e.target.value)} className={claseInput} aria-label="Rol a asignar">
              <option value="perito">Perito oficial</option>
              <option value="perito_parte">Perito de parte</option>
            </select>
            <select value={especialidad} onChange={(e) => setEspecialidad(e.target.value)} className={claseInput} aria-label="Especialidad">
              {Object.entries(ESPECIALIDADES).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <button
              disabled={ocupado}
              onClick={() => enviar("aprobar", { rol, especialidad }, `Cuenta de ${u.nombre} aprobada.`)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui disabled:opacity-60"
            >
              <span className="material-symbols-outlined text-base">how_to_reg</span>Aprobar
            </button>
            <button
              disabled={ocupado}
              onClick={() => setRechazando(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-error/10 text-error font-label-ui text-label-ui hover:bg-error/20 disabled:opacity-60"
            >
              <span className="material-symbols-outlined text-base">block</span>Rechazar
            </button>
          </div>
        )}
      </div>
      {rechazando && (
        <div className="flex flex-wrap items-center gap-space-sm">
          <input
            autoFocus
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            placeholder="Motivo del rechazo (se envía por correo)"
            className={`${claseInput} flex-1 min-w-[16rem]`}
          />
          <button onClick={() => setRechazando(false)} className="px-3 py-1.5 rounded-lg font-label-ui text-label-ui text-on-surface-variant hover:bg-surface-container">
            Cancelar
          </button>
          <button
            disabled={ocupado}
            onClick={() => enviar("rechazar", { motivo }, `Solicitud de ${u.nombre} rechazada.`)}
            className="px-3 py-1.5 rounded-lg bg-error text-on-error font-label-ui text-label-ui disabled:opacity-60"
          >
            Confirmar rechazo
          </button>
        </div>
      )}
    </div>
  );
}

const claseInput =
  "px-2.5 py-2 rounded-md bg-surface-container-lowest text-on-surface font-body-sm text-body-sm focus:outline-none focus:ring-1 focus:ring-primary/50";

export default function Usuarios() {
  const [usuarios, setUsuarios] = useState([]);
  const [error, setError] = useState("");
  const [recarga, setRecarga] = useState(0);
  const [formAbierto, setFormAbierto] = useState(false);
  const [form, setForm] = useState(VACIO);
  const [guardando, setGuardando] = useState(false);
  const yo = useUsuario();
  const navigate = useNavigate();
  const { notificar } = useToast();
  const pendientes = usuarios.filter((u) => u.estado_solicitud === "pendiente");

  useEffect(() => {
    let activo = true;
    api
      .get("/usuarios")
      .then(({ data }) => activo && setUsuarios(data))
      .catch((err) => {
        if (err.response?.status === 401) {
          limpiarSesion();
          navigate("/");
        } else if (activo) {
          setError(err.response?.data?.detail || "No se pudo cargar la lista de usuarios.");
        }
      });
    return () => {
      activo = false;
    };
  }, [recarga, navigate]);

  const cambiar = async (u, cambios, mensaje) => {
    try {
      await api.patch(`/usuarios/${u.id}`, cambios);
      notificar(mensaje, { tipo: "success" });
      setRecarga((n) => n + 1);
    } catch (err) {
      notificar(err.response?.data?.detail || "No se pudo actualizar el usuario.", { tipo: "error" });
      setRecarga((n) => n + 1);
    }
  };
  
  // Sprint 6 (historia 27): levantar un bloqueo por intentos fallidos.
  const desbloquear = async (u) => {
    try {
      await api.post(`/usuarios/${u.id}/desbloquear`);
      notificar(`${u.nombre} fue desbloqueado.`, { tipo: "success" });
    } catch (err) {
      notificar(err.response?.data?.detail || "No se pudo desbloquear.", { tipo: "error" });
    }
    setRecarga((n) => n + 1);
  };

  // Sprint 6 (historia 24): si alguien perdió el celular, se le reinicia el 2FA y se cierran sus sesiones.
  const reiniciar2fa = async (u) => {
    if (!window.confirm(`¿Reiniciar la verificación en dos pasos de ${u.nombre}? Se cerrarán sus sesiones abiertas y tendrá que escanear un QR nuevo.`)) return;
    try {
      await api.post(`/usuarios/${u.id}/reiniciar-2fa`);
      notificar(`Se reinició la verificación en dos pasos de ${u.nombre}.`, { tipo: "success" });
    } catch (err) {
      notificar(err.response?.data?.detail || "No se pudo reiniciar la verificación en dos pasos.", { tipo: "error" });
    }
    setRecarga((n) => n + 1);
  };

  const crear = async (e) => {
    e.preventDefault();
    setGuardando(true);
    try {
      await api.post("/usuarios", { ...form, especialidad: ES_PERITO_ROL(form.rol) ? form.especialidad : null });
      notificar(`Usuario ${form.nombre} creado como ${ETIQUETAS_ROL[form.rol]}.`, { tipo: "success" });
      setForm(VACIO);
      setFormAbierto(false);
      setRecarga((n) => n + 1);
    } catch (err) {
      const d = err.response?.data?.detail;
      notificar(typeof d === "string" ? d : "Revisa los datos del usuario (email válido, contraseña de 10+ con letras y números).", {
        tipo: "error",
      });
    } finally {
      setGuardando(false);
    }
  };

  return (
    <Layout>
      <div className="mb-space-lg flex items-end justify-between gap-space-md flex-wrap">
        <div>
          <h1 className="font-headline-lg text-headline-lg text-on-surface">Usuarios y roles</h1>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            Un usuario desactivado pierde el acceso, pero no se borra: su participación queda en la cadena de custodia.
          </p>
        </div>
        {!formAbierto && (
          <button
            onClick={() => setFormAbierto(true)}
            className="inline-flex items-center gap-2 px-space-md py-2.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui hover:opacity-90"
          >
            <span className="material-symbols-outlined text-base">person_add</span>
            Nuevo usuario
          </button>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 bg-error/10 border border-error/30 rounded-lg px-space-md py-3 text-error font-body-sm text-body-sm mb-space-md">
          <span className="material-symbols-outlined">lock</span>
          {error}
        </div>
      )}

      {formAbierto && (
        <form onSubmit={crear} className="bg-surface-container-low rounded-xl p-space-md mb-space-md flex flex-col gap-space-sm">
          <h2 className="font-headline-sm text-headline-sm text-on-surface">Nuevo usuario</h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-space-sm">
            <input required placeholder="Nombre completo" value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} className={claseInput} />
            <input required type="email" placeholder="Correo" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className={claseInput} />
            <input required type="password" minLength={10} placeholder="Contraseña (10+, letras y números)" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className={claseInput} />
            {/* Sprint 5: solo los peritos tienen especialidad; el fiscal y el jefe, no */}
            {ES_PERITO_ROL(form.rol) ? (
              <select value={form.especialidad} onChange={(e) => setForm({ ...form, especialidad: e.target.value })} className={claseInput}>
                {Object.entries(ESPECIALIDADES).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            ) : (
              <p className={`${claseInput} text-outline`}>Sin especialidad (no es perito)</p>
            )}
            <select value={form.rol} onChange={(e) => setForm({ ...form, rol: e.target.value })} className={claseInput}>
              {Object.entries(ETIQUETAS_ROL).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <p className="font-body-sm text-body-sm text-on-surface-variant self-center">{DESCRIPCION_ROL[form.rol]}</p>
          </div>
          {ES_PERITO_ROL(form.rol) && (
            <div className="grid sm:grid-cols-3 gap-space-sm">
              <input placeholder="Institución (DIRCRI PNP, Medicina Legal…)" value={form.institucion} onChange={(e) => setForm({ ...form, institucion: e.target.value })} className={claseInput} />
              <input placeholder="N° de registro / colegiatura" value={form.registro_profesional} onChange={(e) => setForm({ ...form, registro_profesional: e.target.value })} className={claseInput} />
              <input placeholder="Teléfono" value={form.telefono} onChange={(e) => setForm({ ...form, telefono: e.target.value })} className={claseInput} />
            </div>
          )}
          <div className="flex justify-end gap-space-sm">
            <button type="button" onClick={() => setFormAbierto(false)} className="px-3 py-1.5 rounded-lg font-label-ui text-label-ui text-on-surface-variant hover:bg-surface-container">
              Cancelar
            </button>
            <button type="submit" disabled={guardando} className="px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui disabled:opacity-60">
              {guardando ? "Creando..." : "Crear usuario"}
            </button>
          </div>
        </form>
      )}

      {/* Sprint 6 (historia 25): solicitudes de cuenta por aprobar */}
      {pendientes.length > 0 && (
        <div className="bg-surface-container-low rounded-xl overflow-hidden mb-space-md border border-primary/30">
          <div className="px-space-md py-3 flex items-center gap-2">
            <span className="material-symbols-outlined text-primary">person_search</span>
            <h2 className="font-headline-sm text-headline-sm text-on-surface">Solicitudes pendientes</h2>
            <span className="px-2 py-0.5 rounded-full bg-primary/15 text-primary font-label-ui text-label-ui">{pendientes.length}</span>
          </div>
          {pendientes.map((u) => (
            <SolicitudPendiente key={u.id} u={u} onListo={() => setRecarga((n) => n + 1)} />
          ))}
        </div>
      )}

      <div className="bg-surface-container-low rounded-xl overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-surface-container-lowest">
              {["Usuario", "Especialidad", "Rol", "Casos a cargo", "Estado", "2FA"].map((h) => (
                <th key={h} className="px-space-md py-3 font-label-ui text-label-ui text-outline uppercase tracking-wider">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {usuarios.filter((u) => u.estado_solicitud !== "pendiente").map((u) => {
              const esYo = yo?.id === u.id;
              return (
                <tr key={u.id} className={`border-t border-outline-variant/20 ${u.activo ? "" : "opacity-60"}`}>
                  <td className="px-space-md py-3">
                    <div className="font-body-sm text-body-sm text-on-surface font-semibold">
                      {u.nombre} {esYo && <span className="text-outline font-normal">(tú)</span>}
                    </div>
                    <div className="font-label-code-sm text-label-code-sm text-outline">{u.email}</div>
                    {(u.institucion || u.registro_profesional) && (
                      <div className="font-label-code-sm text-label-code-sm text-outline">
                        {[u.institucion, u.registro_profesional].filter(Boolean).join(" · ")}
                      </div>
                    )}
                  </td>
                  <td className="px-space-md py-3 font-body-sm text-body-sm text-on-surface-variant">
                    {u.especialidad ? ESPECIALIDADES[u.especialidad] : "—"}
                  </td>
                  <td className="px-space-md py-3">
                    <select
                      value={u.rol}
                      disabled={esYo}
                      onChange={(e) =>
                        cambiar(u, { rol: e.target.value }, `${u.nombre} ahora es ${ETIQUETAS_ROL[e.target.value]}.`)
                      }
                      className={`${claseInput} disabled:opacity-60`}
                      title={esYo ? "No puedes cambiar tu propio rol" : DESCRIPCION_ROL[u.rol]}
                    >
                      {Object.entries(ETIQUETAS_ROL).map(([k, v]) => (
                        <option key={k} value={k}>{v}</option>
                      ))}
                    </select>
                  </td>
                  <td className="px-space-md py-3 font-label-code-sm text-label-code-sm text-on-surface">
                    {u.casos_a_cargo}
                  </td>
                  <td className="px-space-md py-3">
                    {u.estado_solicitud === "rechazada" ? (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-error/10 text-error font-label-ui text-label-ui">
                        <span className="material-symbols-outlined text-base">block</span>Solicitud rechazada
                      </span>
                    ) : (
                    <button
                      disabled={esYo}
                      onClick={() =>
                        cambiar(
                          u,
                          { activo: !u.activo },
                          u.activo ? `${u.nombre} fue desactivado.` : `${u.nombre} fue reactivado.`
                        )
                      }
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-label-ui text-label-ui disabled:opacity-40 ${
                        u.activo ? "bg-tertiary/10 text-tertiary hover:bg-tertiary/20" : "bg-error/10 text-error hover:bg-error/20"
                      }`}
                    >
                      <span className="material-symbols-outlined text-base">{u.activo ? "toggle_on" : "toggle_off"}</span>
                      {u.activo ? "Activo" : "Desactivado"}
                    </button>
                    )}
                    {u.bloqueado_hasta && new Date(u.bloqueado_hasta) > new Date() && (
                      <div className="mt-1.5 flex flex-wrap items-center gap-2">
                        <span className="inline-flex items-center gap-1 font-label-ui text-label-ui text-error">
                          <span className="material-symbols-outlined text-base">lock_clock</span>
                          Bloqueado hasta {new Date(u.bloqueado_hasta).toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit" })}
                        </span>
                        <button onClick={() => desbloquear(u)} className="font-label-ui text-label-ui text-primary hover:underline">
                          Desbloquear
                        </button>
                      </div>
                    )}
                  </td>
                  {/* Sprint 6 (historia 24) */}
                  <td className="px-space-md py-3">
                    {u.totp_activo ? (
                      <div className="flex flex-col items-start gap-1">
                        <span className="inline-flex items-center gap-1 font-label-ui text-label-ui text-tertiary">
                          <span className="material-symbols-outlined text-base">verified_user</span>
                          Activa
                        </span>
                        {!esYo && (
                          <button onClick={() => reiniciar2fa(u)} className="font-label-ui text-label-ui text-primary hover:underline">
                            Reiniciar 2FA
                          </button>
                        )}
                      </div>
                    ) : ROLES_CON_2FA.includes(u.rol) ? (
                      <span
                        className="inline-flex items-center gap-1 font-label-ui text-label-ui text-on-surface-variant"
                        title="Su rol exige 2FA: la configurará en su próximo ingreso."
                      >
                        <span className="material-symbols-outlined text-base">pending</span>
                        Pendiente
                      </span>
                    ) : (
                      <span className="font-body-sm text-body-sm text-outline">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}