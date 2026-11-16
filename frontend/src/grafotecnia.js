// Sprint 7 (historia 28): utilidades de la especialidad grafotecnia.

export const ROLES_GRAFOTECNICOS = {
  dubitado: {
    texto: "Dubitado",
    ayuda: "Documento cuestionado: su firma o texto es lo que se analiza.",
    clase: "bg-error/10 text-error border-error/30",
  },
  indubitado: {
    texto: "Indubitado",
    ayuda: "Autoría conocida: sirve de patrón de comparación.",
    clase: "bg-tertiary/10 text-tertiary border-tertiary/30",
  },
};

export const esCasoGrafotecnia = (caso) =>
  (caso.especialidades?.length ? caso.especialidades : [caso.especialidad]).includes("grafotecnia");

// Imagen o PDF según el contenido real detectado al subir (como hace la API).
export function esVisualizable(a) {
  const mime = a.metadatos_tecnicos?.mime_detectado || "";
  if (mime) return mime === "application/pdf" || mime.startsWith("image/");
  return /\.(pdf|jpe?g|png|tiff?|bmp|gif|webp)$/i.test(a.nombre_original);
}
