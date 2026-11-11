// Sprint 6 (historia 25): sesión persistente.
// Con "Recordarme" los tokens se guardan en localStorage (sobreviven a cerrar el
// navegador, hasta 30 días). Sin marcarlo van a sessionStorage: la sesión termina
// al cerrar la pestaña/navegador y el refresh token dura solo 12 horas.

const CLAVES = ["access_token", "refresh_token"];

function almacen() {
  return sessionStorage.getItem("access_token") ? sessionStorage : localStorage;
}

export function guardarSesion({ access_token, refresh_token }, recordar) {
  limpiarSesion();
  const destino = recordar ? localStorage : sessionStorage;
  destino.setItem("access_token", access_token);
  destino.setItem("refresh_token", refresh_token);
}

// Tras renovar los tokens se guardan donde ya estaban.
export function actualizarTokens({ access_token, refresh_token }) {
  const destino = almacen();
  destino.setItem("access_token", access_token);
  destino.setItem("refresh_token", refresh_token);
}

export function obtenerAccessToken() {
  return sessionStorage.getItem("access_token") || localStorage.getItem("access_token");
}

export function obtenerRefreshToken() {
  return sessionStorage.getItem("refresh_token") || localStorage.getItem("refresh_token");
}

export function limpiarSesion() {
  CLAVES.forEach((k) => {
    localStorage.removeItem(k);
    sessionStorage.removeItem(k);
  });
}