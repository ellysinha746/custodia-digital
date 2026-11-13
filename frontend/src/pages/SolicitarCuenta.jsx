import { useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import PantallaAcceso, { claseCampo } from "../components/PantallaAcceso";

// Sprint 6 (historia 25): un perito pide su cuenta; queda pendiente hasta que
// el jefe de laboratorio la aprueba. Nadie entra al sistema solo por registrarse.

const ESPECIALIDADES = { informatica: "Informática", telefonia: "Telefonía", audio: "Audio", video: "Video" };

const VACIO = {
  nombre: "", email: "", password: "", confirmar: "", rol: "perito", especialidad: "informatica",
  institucion: "", registro_profesional: "", telefono: "",
};

function Campo({ etiqueta, children, ayuda }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="font-label-ui text-label-ui text-on-surface-variant">{etiqueta}</span>
      {children}
      {ayuda && <span className="font-body-sm text-body-sm text-outline">{ayuda}</span>}
    </label>
  );
}

export default function SolicitarCuenta() {
  const [form, setForm] = useState(VACIO);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [enviada, setEnviada] = useState(null);
  const cambiar = (campo) => (e) => setForm({ ...form, [campo]: e.target.value });

  const enviar = async (e) => {
    e.preventDefault();
    setError("");
    if (form.password !== form.confirmar) {
      setError("Las contraseñas no coinciden.");
      return;
    }
    setEnviando(true);
    try {
      const { confirmar, ...datos } = form; // eslint-disable-line no-unused-vars
      await api.post("/auth/registro", datos);
      setEnviada(form.email);
    } catch (err) {
      const d = err.response?.data?.detail;
      setError(typeof d === "string" ? d : "Revisa los datos (correo válido y contraseña de 8 caracteres o más).");
    } finally {
      setEnviando(false);
    }
  };

  if (enviada) {
    return (
      <PantallaAcceso titulo="Solicitud enviada">
        <div className="flex items-start gap-space-sm bg-tertiary/10 border border-tertiary/30 rounded-lg p-space-md">
          <span className="material-symbols-outlined text-tertiary">mark_email_read</span>
          <p className="font-body-sm text-body-sm text-on-surface">
            Tu solicitud quedó registrada. El jefe de laboratorio la revisará y te avisaremos a <strong>{enviada}</strong>{" "}
            cuando tu cuenta esté aprobada. Mientras tanto no podrás iniciar sesión.
          </p>
        </div>
        <Link to="/" className="font-label-ui text-label-ui text-primary hover:underline">
          Volver a iniciar sesión
        </Link>
      </PantallaAcceso>
    );
  }

  return (
    <PantallaAcceso
      ancho="max-w-2xl"
      titulo="Solicitar acceso"
      subtitulo="Para peritos oficiales y peritos de parte. El jefe de laboratorio aprobará tu cuenta antes de que puedas entrar."
    >
      <form onSubmit={enviar} className="flex flex-col gap-space-md">
        <div className="grid sm:grid-cols-2 gap-space-sm">
          <Campo etiqueta="Nombre completo">
            <input required value={form.nombre} onChange={cambiar("nombre")} className={claseCampo} />
          </Campo>
          <Campo etiqueta="Correo">
            <input required type="email" value={form.email} onChange={cambiar("email")} className={claseCampo} />
          </Campo>
          <Campo etiqueta="Contraseña" ayuda="Mínimo 10 caracteres, con letras y números.">
            <input required type="password" minLength={10} autoComplete="new-password" value={form.password} onChange={cambiar("password")} className={claseCampo} />
          </Campo>
          <Campo etiqueta="Repite la contraseña">
            <input required type="password" minLength={10} autoComplete="new-password" value={form.confirmar} onChange={cambiar("confirmar")} className={claseCampo} />
          </Campo>
          <Campo etiqueta="Tipo de perito">
            <select value={form.rol} onChange={cambiar("rol")} className={claseCampo}>
              <option value="perito">Perito oficial</option>
              <option value="perito_parte">Perito de parte</option>
            </select>
          </Campo>
          <Campo etiqueta="Especialidad">
            <select value={form.especialidad} onChange={cambiar("especialidad")} className={claseCampo}>
              {Object.entries(ESPECIALIDADES).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </Campo>
          <Campo etiqueta="Institución">
           <input required placeholder="DIRCRI PNP, Medicina Legal, perito particular…" value={form.institucion} onChange={cambiar("institucion")} className={claseCampo} />
          </Campo>
          <Campo etiqueta="N° de registro / colegiatura">
           <input required value={form.registro_profesional} onChange={cambiar("registro_profesional")} className={claseCampo} />
          </Campo>
          <Campo etiqueta="Teléfono">
            <input value={form.telefono} onChange={cambiar("telefono")} className={claseCampo} />
          </Campo>
        </div>
        {error && (
          <p className="flex items-start gap-2 bg-error/10 border border-error/30 rounded-md px-3 py-2 text-error font-body-sm text-body-sm">
            <span className="material-symbols-outlined text-base mt-0.5">error</span>
            {error}
          </p>
        )}
        <div className="flex flex-wrap items-center justify-between gap-space-sm">
          <Link to="/" className="font-label-ui text-label-ui text-on-surface-variant hover:underline">
            Ya tengo cuenta
          </Link>
          <button
            type="submit"
            disabled={enviando}
            className="px-space-md py-2.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui hover:opacity-90 disabled:opacity-60"
          >
            {enviando ? "Enviando..." : "Enviar solicitud"}
          </button>
        </div>
      </form>
    </PantallaAcceso>
  );
}