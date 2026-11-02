import { useEffect, useState } from "react";
import api from "./api";

// Sprint 5 (historia 19.1): roles y permisos en el frontend.
// Es un espejo de backend/app/core/permisos.py: el front solo OCULTA botones;
// quien realmente bloquea es el backend (responde 403).

export const ETIQUETAS_ROL = {
  admin: "Jefe de laboratorio",
  perito: "Perito oficial",
  perito_parte: "Perito de parte",
  fiscal: "Fiscal / Auditor",
};

const PERMISOS = {
  crear_caso: ["admin", "perito"],
  cambiar_estado_caso: ["admin", "perito"],
  eliminar_caso: ["admin", "perito"],
  papelera: ["admin", "perito"],
  subir_evidencia: ["admin", "perito"],
  editar_metadatos: ["admin", "perito"],
  registrar_ficha: ["admin", "perito"],
  verificar_integridad: ["admin", "perito", "perito_parte"],
  verificar_dispositivo: ["admin", "perito"],
  descargar_original: ["admin", "perito", "fiscal"],
  subir_observada: ["admin", "perito", "perito_parte"],
  atender_alertas: ["admin"],
  ver_dashboard: ["admin"],
  gestionar_usuarios: ["admin"],
};

export function puede(usuario, accion) {
  return !!usuario && (PERMISOS[accion] || []).includes(usuario.rol);
}

// Se pide /auth/me una sola vez y se comparte entre todas las pantallas.
let promesaUsuario = null;

export function olvidarUsuario() {
  promesaUsuario = null;
}

export function useUsuario() {
  const [usuario, setUsuario] = useState(null);
  useEffect(() => {
    let activo = true;
    if (!promesaUsuario) {
      promesaUsuario = api.get("/auth/me").then(({ data }) => data);
      promesaUsuario.catch(() => {
        promesaUsuario = null;
      });
    }
    promesaUsuario.then((u) => activo && setUsuario(u)).catch(() => {});
    return () => {
      activo = false;
    };
  }, []);
  return usuario;
}
