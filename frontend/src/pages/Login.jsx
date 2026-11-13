import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../api";
import { olvidarUsuario } from "../permisos";
import { guardarSesion, limpiarSesion, obtenerAccessToken } from "../sesion";
import PantallaAcceso, { claseCampo } from "../components/PantallaAcceso";

const claseBoton =
  "mt-1 px-space-md py-2.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui hover:opacity-90 disabled:opacity-60";
const claseCodigo = `${claseCampo} font-label-code-sm text-label-code-sm tracking-[0.4em] text-center`;

// Sprint 6 (historia 24): deja solo dígitos (máximo 6) en un campo de código.
const soloDigitos = (v) => v.replace(/\D/g, "").slice(0, 6);

function AvisoError({ texto }) {
  if (!texto) return null;
  return (
    <p className="flex items-start gap-2 bg-error/10 border border-error/30 rounded-md px-3 py-2 text-error font-body-sm text-body-sm">
      <span className="material-symbols-outlined text-base mt-0.5">error</span>
      {texto}
    </p>
  );
}

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [recordarme, setRecordarme] = useState(false);
  const [error, setError] = useState("");
  const [entrando, setEntrando] = useState(false);
  // Sprint 6 (historia 24): "credenciales" → "codigo" (2FA ya activo) o "configurar" (primer ingreso)
  const [etapa, setEtapa] = useState("credenciales");
  const [token2fa, setToken2fa] = useState("");
  const [config2fa, setConfig2fa] = useState(null); // { qr, secreto, correo }
  const [codigo, setCodigo] = useState("");
  const [codigoCorreo, setCodigoCorreo] = useState("");
  const navigate = useNavigate();

  // Sprint 6 (historia 25): si ya hay una sesión guardada y sigue válida, se entra directo.
  useEffect(() => {
    if (!obtenerAccessToken()) return;
    api
      .get("/auth/me")
      .then(() => navigate("/casos"))
      .catch(() => limpiarSesion());
  }, [navigate]);

  const entrar = (data) => {
    guardarSesion(data, recordarme);
    olvidarUsuario(); // Sprint 5: que se vuelva a leer el rol del usuario que entra
    navigate("/casos");
  };

  const volverAlInicio = (mensaje = "") => {
    setEtapa("credenciales");
    setToken2fa("");
    setConfig2fa(null);
    setCodigo("");
    setCodigoCorreo("");
    setPassword("");
    setError(mensaje);
  };

  // Error en un paso del 2FA: si expiró el pase o se bloqueó la cuenta, se vuelve a la contraseña.
  const errorEn2fa = (err) => {
    const detalle = err.response?.data?.detail || "No se pudo verificar el código.";
    if (err.response?.status === 429 || detalle.includes("expiró")) volverAlInicio(detalle);
    else setError(detalle);
  };

  const pedirQr = async (token) => {
    const { data } = await api.post("/auth/2fa/configurar", { token_2fa: token });
    setConfig2fa(data);
    setCodigo("");
    setCodigoCorreo("");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setEntrando(true);
    try {
      const { data } = await api.post("/auth/login", { email, password, recordarme });
      if (!data.requiere_2fa) return entrar(data);
      // Sprint 6 (historia 24): la contraseña es correcta, falta el segundo paso.
      setToken2fa(data.token_2fa);
      if (data.configurar_2fa) {
        await pedirQr(data.token_2fa);
        setEtapa("configurar");
      } else {
        setEtapa("codigo");
      }
    } catch (err) {
      // 403: cuenta desactivada/pendiente/rechazada · 429: bloqueada por intentos fallidos (H27)
      const conMensaje = [403, 429].includes(err.response?.status);
      setError(conMensaje ? err.response.data.detail : "Email o contraseña incorrectos.");
    } finally {
      setEntrando(false);
    }
  };

  const verificar = async (e) => {
    e.preventDefault();
    setError("");
    setEntrando(true);
    try {
      const { data } = await api.post("/auth/2fa/verificar", { token_2fa: token2fa, codigo });
      entrar(data);
    } catch (err) {
      setCodigo("");
      errorEn2fa(err);
    } finally {
      setEntrando(false);
    }
  };

  const activar = async (e) => {
    e.preventDefault();
    setError("");
    setEntrando(true);
    try {
      const { data } = await api.post("/auth/2fa/activar", {
        token_2fa: token2fa,
        codigo,
        codigo_correo: codigoCorreo,
      });
      entrar(data);
    } catch (err) {
      setCodigo("");
      errorEn2fa(err);
    } finally {
      setEntrando(false);
    }
  };

  const reenviar = async () => {
    setError("");
    try {
      await pedirQr(token2fa);
    } catch (err) {
      errorEn2fa(err);
    }
  };

  const enlaceVolver = (
    <button
      type="button"
      onClick={() => volverAlInicio()}
      className="self-start font-body-sm text-body-sm text-primary hover:underline"
    >
      ← Volver e ingresar con otra cuenta
    </button>
  );

  // Sprint 6 (historia 24): segundo paso del login.
  if (etapa === "codigo") {
    return (
      <PantallaAcceso titulo="Verificación en dos pasos" subtitulo="Escribe el código de 6 dígitos de tu app autenticadora.">
        <form onSubmit={verificar} className="flex flex-col gap-space-sm">
          <label className="flex flex-col gap-1">
            <span className="font-label-ui text-label-ui text-on-surface-variant">Código de la app</span>
            <input
              autoFocus
              required
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="\d{6}"
              placeholder="000000"
              value={codigo}
              onChange={(e) => setCodigo(soloDigitos(e.target.value))}
              className={claseCodigo}
            />
          </label>
          <AvisoError texto={error} />
          <button type="submit" disabled={entrando || codigo.length !== 6} className={claseBoton}>
            {entrando ? "Verificando..." : "Verificar e ingresar"}
          </button>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            ¿Perdiste el celular? Pide al jefe de laboratorio que reinicie tu verificación en dos pasos.
          </p>
          {enlaceVolver}
        </form>
      </PantallaAcceso>
    );
  }

  // Sprint 6 (historia 24): primer ingreso de un jefe o fiscal, registrar la app autenticadora.
  if (etapa === "configurar" && config2fa) {
    const secretoAgrupado = config2fa.secreto.match(/.{1,4}/g).join(" ");
    return (
      <PantallaAcceso
        titulo="Activa la verificación en dos pasos"
        subtitulo="Tu rol la exige. Solo se hace una vez y tarda un minuto."
        ancho="max-w-lg"
      >
        <form onSubmit={activar} className="flex flex-col gap-space-md">
          <ol className="flex flex-col gap-space-md font-body-sm text-body-sm text-on-surface">
            <li>
              <span className="font-semibold">1.</span> Instala en tu celular una app autenticadora: Google
              Authenticator, Microsoft Authenticator o Authy.
            </li>
            <li className="flex flex-col gap-2">
              <span>
                <span className="font-semibold">2.</span> En la app, agrega una cuenta y escanea este código QR:
              </span>
              <img
                src={config2fa.qr}
                alt="Código QR para la app autenticadora"
                className="self-center w-48 h-48 rounded-md bg-white p-1"
              />
              <span className="text-on-surface-variant">
                ¿No puedes escanearlo? Escribe esta clave en la app:{" "}
                <span className="font-label-code-sm text-label-code-sm text-on-surface break-words">{secretoAgrupado}</span>
              </span>
            </li>
            <li className="flex flex-col gap-1">
              <span>
                <span className="font-semibold">3.</span> Te enviamos un código a{" "}
                <span className="font-semibold">{config2fa.correo}</span>. Escríbelo aquí junto con el que muestra la app.
              </span>
            </li>
          </ol>
          <div className="grid sm:grid-cols-2 gap-space-sm">
            <label className="flex flex-col gap-1">
              <span className="font-label-ui text-label-ui text-on-surface-variant">Código del correo</span>
              <input
                required
                inputMode="numeric"
                pattern="\d{6}"
                placeholder="000000"
                value={codigoCorreo}
                onChange={(e) => setCodigoCorreo(soloDigitos(e.target.value))}
                className={claseCodigo}
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="font-label-ui text-label-ui text-on-surface-variant">Código de la app</span>
              <input
                required
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="\d{6}"
                placeholder="000000"
                value={codigo}
                onChange={(e) => setCodigo(soloDigitos(e.target.value))}
                className={claseCodigo}
              />
            </label>
          </div>
          <AvisoError texto={error} />
          <button
            type="submit"
            disabled={entrando || codigo.length !== 6 || codigoCorreo.length !== 6}
            className={claseBoton}
          >
            {entrando ? "Activando..." : "Activar y entrar"}
          </button>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            ¿No te llegó el correo?{" "}
            <button type="button" onClick={reenviar} className="text-primary hover:underline">
              Generar un QR y un código nuevos
            </button>{" "}
            (el QR anterior deja de servir: vuelve a escanearlo).
          </p>
          {enlaceVolver}
        </form>
      </PantallaAcceso>
    );
  }

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
        <AvisoError texto={error} />
        <button type="submit" disabled={entrando} className={claseBoton}>
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
