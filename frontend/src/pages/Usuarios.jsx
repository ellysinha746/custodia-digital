import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
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
  fiscal: "Solo lectura de todos los casos, auditoría y reportes.",
};

const VACIO = { nombre: "", email: "", password: "", especialidad: "telefonia", rol: "perito" };

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

  useEffect(() => {
    let activo = true;
    api
      .get("/usuarios")
      .then(({ data }) => activo && setUsuarios(data))
      .catch((err) => {
        if (err.response?.status === 401) {
          localStorage.clear();
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

  const crear = async (e) => {
    e.preventDefault();
    setGuardando(true);
    try {
      await api.post("/usuarios", form);
      notificar(`Usuario ${form.nombre} creado como ${ETIQUETAS_ROL[form.rol]}.`, { tipo: "success" });
      setForm(VACIO);
      setFormAbierto(false);
      setRecarga((n) => n + 1);
    } catch (err) {
      const d = err.response?.data?.detail;
      notificar(typeof d === "string" ? d : "Revisa los datos del usuario (email válido, contraseña de 8+).", {
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
            <input required type="password" minLength={8} placeholder="Contraseña (8+ caracteres)" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className={claseInput} />
            <select value={form.especialidad} onChange={(e) => setForm({ ...form, especialidad: e.target.value })} className={claseInput}>
              {Object.entries(ESPECIALIDADES).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <select value={form.rol} onChange={(e) => setForm({ ...form, rol: e.target.value })} className={claseInput}>
              {Object.entries(ETIQUETAS_ROL).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <p className="font-body-sm text-body-sm text-on-surface-variant self-center">{DESCRIPCION_ROL[form.rol]}</p>
          </div>
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

      <div className="bg-surface-container-low rounded-xl overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-surface-container-lowest">
              {["Usuario", "Especialidad", "Rol", "Casos a cargo", "Estado"].map((h) => (
                <th key={h} className="px-space-md py-3 font-label-ui text-label-ui text-outline uppercase tracking-wider">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {usuarios.map((u) => {
              const esYo = yo?.id === u.id;
              return (
                <tr key={u.id} className={`border-t border-outline-variant/20 ${u.activo ? "" : "opacity-60"}`}>
                  <td className="px-space-md py-3">
                    <div className="font-body-sm text-body-sm text-on-surface font-semibold">
                      {u.nombre} {esYo && <span className="text-outline font-normal">(tú)</span>}
                    </div>
                    <div className="font-label-code-sm text-label-code-sm text-outline">{u.email}</div>
                  </td>
                  <td className="px-space-md py-3 font-body-sm text-body-sm text-on-surface-variant">
                    {ESPECIALIDADES[u.especialidad]}
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
