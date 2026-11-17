// Sprint 7 (historia 28): especialidades en un solo lugar (antes estaban copiadas en 9 pantallas).

export const ESPECIALIDADES_INFO = {
  informatica: { label: "Informática", icon: "computer" },
  telefonia: { label: "Telefonía", icon: "smartphone" },
  audio: { label: "Audio", icon: "graphic_eq" },
  video: { label: "Video", icon: "videocam" },
  grafotecnia: { label: "Grafotecnia", icon: "signature" }, // documentos y firmas
};

// { informatica: "Informática", ... } para selects y textos.
export const ESPECIALIDADES = Object.fromEntries(
  Object.entries(ESPECIALIDADES_INFO).map(([clave, { label }]) => [clave, label])
);
