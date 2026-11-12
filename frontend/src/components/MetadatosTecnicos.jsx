import { useState } from "react";
import api from "../api";
import { useToast } from "./Toast";

// Sprint 6 (historia 20): metadatos técnicos extraídos automáticamente al subir
// (tipo real del archivo, EXIF, ffprobe, PDF). El perito no los escribe: los lee el sistema.

const ICONO_CATEGORIA = {
  imagen: "image",
  video: "movie",
  audio: "graphic_eq",
  documento: "picture_as_pdf",
  otro: "draft",
};

function tamanoLegible(bytes) {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

// Archivos subidos antes del Sprint 6 pueden tener "campos" como objeto.
function listaCampos(campos) {
  if (Array.isArray(campos)) return campos;
  return Object.entries(campos || {}).map(([campo, valor]) => ({ campo, valor }));
}

export default function MetadatosTecnicos({ archivo, puedeExtraer, onCambio, onHistorial }) {
  const [extrayendo, setExtrayendo] = useState(false);
  const { notificar } = useToast();
  const m = archivo.metadatos_tecnicos;

  const extraer = async () => {
    setExtrayendo(true);
    try {
      await api.post(`/archivos/${archivo.id}/metadatos-tecnicos`);
      notificar("Metadatos técnicos extraídos del original.", { tipo: "success" });
      onCambio?.();
      onHistorial?.();
    } catch (err) {
      notificar(err.response?.data?.detail || "No se pudieron extraer los metadatos.", { tipo: "error" });
    } finally {
      setExtrayendo(false);
    }
  };

  const boton = puedeExtraer && (
    <button
      onClick={extraer}
      disabled={extrayendo}
      className="inline-flex items-center gap-1 font-label-ui text-label-ui text-primary hover:underline disabled:opacity-60"
    >
      <span className="material-symbols-outlined text-base">refresh</span>
      {extrayendo ? "Extrayendo..." : m ? "Volver a extraer" : "Extraer ahora"}
    </button>
  );

  if (!m) {
    return (
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="font-label-ui text-label-ui text-outline uppercase tracking-wider">Metadatos técnicos</span>
          {boton}
        </div>
        <p className="font-body-sm text-body-sm text-outline">
          Este archivo se subió antes de la extracción automática.
        </p>
      </div>
    );
  }

  const campos = listaCampos(m.campos);
  const noCoincide = m.extension_coincide === false;
  const otrosAvisos = (m.avisos || []).filter((a) => !(noCoincide && a.startsWith("La extensión")));

  return (
    <div>
      <div className="flex items-center justify-between mb-1 gap-space-sm flex-wrap">
        <span className="font-label-ui text-label-ui text-outline uppercase tracking-wider">
          Metadatos técnicos · automáticos
        </span>
        {boton}
      </div>

      <div className="bg-surface-container-high rounded-lg p-space-sm flex flex-col gap-space-sm">
        <div className="flex flex-wrap items-center gap-x-space-md gap-y-1 font-body-sm text-body-sm text-on-surface-variant">
          <span className="inline-flex items-center gap-1.5 text-on-surface">
            <span className="material-symbols-outlined text-base text-primary">{ICONO_CATEGORIA[m.categoria] || "draft"}</span>
            {m.mime_detectado || "Tipo no reconocido por su contenido"}
          </span>
          <span>{tamanoLegible(m.tamano_bytes)}</span>
          {m.almacenamiento && (
            <span className="inline-flex items-center gap-1">
              <span className="material-symbols-outlined text-base">cloud</span>
              {m.almacenamiento}
            </span>
          )}
          {m.extension_coincide === true && (
            <span className="inline-flex items-center gap-1 text-tertiary">
              <span className="material-symbols-outlined text-base">check_circle</span>
              La extensión coincide con el contenido
            </span>
          )}
        </div>

        {noCoincide && (
          <div className="flex items-start gap-2 bg-error/10 border border-error/30 rounded-md px-space-sm py-2 text-error font-body-sm text-body-sm">
            <span className="material-symbols-outlined text-base mt-0.5">warning</span>
            <span>
              La extensión <strong>.{m.extension_declarada || "(ninguna)"}</strong> no coincide con el contenido real
              del archivo (<strong>{m.mime_detectado}</strong>, extensión esperada .{m.extension_real}). Puede haber sido
              renombrado para ocultar su tipo.
            </span>
          </div>
        )}

        {campos.length > 0 && (
          <dl className="grid sm:grid-cols-2 gap-x-space-md gap-y-1">
            {campos.map((c) => (
              <div key={c.campo} className="flex justify-between sm:justify-start sm:gap-2 min-w-0">
                <dt className="font-body-sm text-body-sm text-on-surface-variant shrink-0">{c.campo}:</dt>
                <dd className="font-label-code-sm text-label-code-sm text-on-surface truncate" title={String(c.valor)}>
                  {String(c.valor)}
                </dd>
              </div>
            ))}
          </dl>
        )}

        {m.gps && (
          <div className="flex flex-wrap items-center gap-space-sm font-body-sm text-body-sm">
            <span className="inline-flex items-center gap-1 text-on-surface">
              <span className="material-symbols-outlined text-base text-primary">location_on</span>
              GPS: {m.gps.lat}, {m.gps.lon}
            </span>
            <a
              href={`https://www.openstreetmap.org/?mlat=${m.gps.lat}&mlon=${m.gps.lon}#map=17/${m.gps.lat}/${m.gps.lon}`}
              target="_blank"
              rel="noreferrer"
              className="text-primary hover:underline"
            >
              Ver en el mapa
            </a>
          </div>
        )}

        {otrosAvisos.length > 0 && (
          <ul className="flex flex-col gap-1">
            {otrosAvisos.map((a) => (
              <li key={a} className="flex items-start gap-1.5 font-body-sm text-body-sm text-on-surface-variant">
                <span className="material-symbols-outlined text-base text-outline">info</span>
                {a}
              </li>
            ))}
          </ul>
        )}

        <p className="font-label-code-sm text-label-code-sm text-outline">
          Extraído con {(m.herramientas || []).join(", ") || "—"}
        </p>
      </div>
    </div>
  );
}