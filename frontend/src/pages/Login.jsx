import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../api";
import { olvidarUsuario } from "../permisos";
import { guardarSesion, limpiarSesion, obtenerAccessToken } from "../sesion";
import PantallaAcceso, { claseCampo } from "../components/PantallaAcceso";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [recordarme, setRecordarme] = useState(false);
  const [error, setError] = useState("");
  const [entrando, setEntrando] = useState(false);
  const navigate = useNavigate();

  // Sprint 6 (historia 25): si ya hay una sesión guardada y sigue válida, se entra directo.
  useEffect(() => {
    if (!obtenerAccessToken()) return;
    api
      .get("/auth/me")
      .then(() => navigate("/casos"))
      .catch(() => limpiarSesion());
  }, [navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setEntrando(true);
    try {
      const { data } = await api.post("/auth/login", { email, password, recordarme });
      guardarSesion(data, recordarme);
      olvidarUsuario(); // Sprint 5: que se vuelva a leer el rol del usuario que entra
      navigate("/casos");
    } catch (err) {
      // Sprint 5/6: cuenta desactivada, pendiente o rechazada → 403 con su propio mensaje
      setError(err.response?.status === 403 ? err.response.data.detail : "Email o contraseña incorrectos.");
    } finally {
      setEntrando(false);
    }
  };

  return (
    <PantallaAcceso titulo="Iniciar sesión" subtitulo="Ingresa con tu cuenta del laboratorio.">
      <form onSubmit={handleSubmit} className="flex flex-col gap-space-sm">
        <label className="flex flex-col gap-1">
          <span className="font-label-ui text-label-ui text-on-surface-variant">Correo</span>
          <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required className={claseCampo} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="font-label-ui text-label-ui text-on-surface-variant">Contraseña</span>
          <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required className={claseCampo} />
        </label>
        <label className="flex items-start gap-2 mt-1 cursor-pointer">
          <input type="checkbox" checked={recordarme} onChange={(e) => setRecordarme(e.target.checked)} className="mt-1 accent-primary" />
          <span className="font-body-sm text-body-sm text-on-surface">
            Recordarme en este equipo
            <span className="block text-on-surface-variant">
              La sesión se mantiene hasta 30 días. No lo marques en una computadora compartida.
            </span>
          </span>
        </label>
        {error && (
          <p className="flex items-start gap-2 bg-error/10 border border-error/30 rounded-md px-3 py-2 text-error font-body-sm text-body-sm">
            <span className="material-symbols-outlined text-base mt-0.5">error</span>
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={entrando}
          className="mt-1 px-space-md py-2.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui hover:opacity-90 disabled:opacity-60"
        >
          {entrando ? "Ingresando..." : "Ingresar"}
        </button>
      </form>
      <p className="font-body-sm text-body-sm text-on-surface-variant border-t border-outline-variant/30 pt-space-md">
        ¿Eres perito y no tienes cuenta?{" "}
        <Link to="/solicitar" className="text-primary hover:underline">
          Solicitar acceso
        </Link>
      </p>
    </PantallaAcceso>
  );
}