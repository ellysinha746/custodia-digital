import axios from "axios";
import { actualizarTokens, limpiarSesion, obtenerAccessToken, obtenerRefreshToken } from "./sesion";

const BASE = "http://localhost:8000";
const api = axios.create({ baseURL: BASE });

api.interceptors.request.use((config) => {
  const token = obtenerAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Sprint 6 (historia 25): el access token dura 30 minutos. Cuando vence, se pide
// uno nuevo con el refresh token y se reintenta la petición, sin sacar al usuario.
let renovando = null;

function renovarTokens() {
  if (!renovando) {
    const refresh_token = obtenerRefreshToken();
    renovando = (refresh_token
      ? axios.post(`${BASE}/auth/refresh`, { refresh_token }).then(({ data }) => {
          actualizarTokens(data);
          return data.access_token;
        })
      : Promise.reject(new Error("sin refresh token"))
    ).finally(() => {
      renovando = null;
    });
  }
  return renovando;
}

api.interceptors.response.use(
  (respuesta) => respuesta,
  async (error) => {
    const original = error.config;
    // Sprint 6 (historia 24): un código 2FA incorrecto (401) tampoco debe intentar renovar la sesión.
    const esAuth = ["/auth/login", "/auth/refresh", "/auth/2fa"].some((r) => original?.url?.startsWith(r));
    if (error.response?.status === 401 && original && !original._reintento && !esAuth && obtenerRefreshToken()) {
      original._reintento = true;
      try {
        const nuevo = await renovarTokens();
        original.headers.Authorization = `Bearer ${nuevo}`;
        return api(original);
      } catch {
        limpiarSesion(); // la sesión expiró de verdad: cada pantalla redirige al login con el 401
      }
    }
    return Promise.reject(error);
  }
);

export default api;