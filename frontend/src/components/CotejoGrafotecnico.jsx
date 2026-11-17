import { useEffect, useRef, useState } from "react";
import api from "../api";
import { InsigniaRol } from "./RolGrafotecnico";
import { esVisualizable } from "../grafotecnia";

// Sprint 7 (historia 28): cotejo grafotécnico lado a lado. A la izquierda el documento
// dubitado y a la derecha un indubitado, con el mismo zoom y (si se quiere) el mismo
// desplazamiento, para comparar trazos de firma o letra en el mismo punto de ambos.

const claseSelect =
  "flex-1 min-w-0 px-2.5 py-1.5 rounded-md bg-surface-container-lowest text-on-surface font-body-sm text-body-sm border border-outline-variant/40 focus:outline-none focus:ring-1 focus:ring-primary/50";

function Visor({ archivos, archivoId, onArchivo, zoom, onZoom, scroll, onScroll }) {
  const [pagina, setPagina] = useState(1);
  const [imagen, setImagen] = useState({ clave: null, url: null, paginas: 1, error: null });
  const caja = useRef(null);
  const arrastre = useRef(null);
  const aplicando = useRef(false);
  const clave = `${archivoId}|${pagina}`;
  const archivo = archivos.find((a) => a.id === archivoId);

  // Descarga la página como imagen (la API la convierte desde la copia de trabajo).
  useEffect(() => {
    if (!archivoId) return undefined;
    let vigente = true;
    let url = null;
    api
      .get(`/archivos/${archivoId}/vista`, { params: { pagina }, responseType: "blob" })
      .then(({ data, headers }) => {
        if (!vigente) return;
        url = URL.createObjectURL(data);
        setImagen({ clave, url, paginas: Number(headers["x-paginas"] || 1), error: null });
      })
      .catch(() => vigente && setImagen({ clave, url: null, paginas: 1, error: "No se pudo mostrar este documento." }));
    return () => {
      vigente = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [archivoId, pagina, clave]);

  // Desplazamiento sincronizado: se aplica la posición relativa que llega del otro visor.
  useEffect(() => {
    const c = caja.current;
    if (!c || !scroll) return;
    aplicando.current = true;
    c.scrollLeft = scroll.x * (c.scrollWidth - c.clientWidth);
    c.scrollTop = scroll.y * (c.scrollHeight - c.clientHeight);
    requestAnimationFrame(() => (aplicando.current = false));
  }, [scroll]);

  const alDesplazar = () => {
    const c = caja.current;
    if (!c || aplicando.current) return;
    onScroll({
      x: c.scrollWidth > c.clientWidth ? c.scrollLeft / (c.scrollWidth - c.clientWidth) : 0,
      y: c.scrollHeight > c.clientHeight ? c.scrollTop / (c.scrollHeight - c.clientHeight) : 0,
    });
  };

  // Arrastrar con el mouse para moverse por la imagen ampliada; Ctrl + rueda para el zoom.
  const empezar = (e) => {
    arrastre.current = { x: e.clientX, y: e.clientY, left: caja.current.scrollLeft, top: caja.current.scrollTop };
  };
  const mover = (e) => {
    if (!arrastre.current) return;
    caja.current.scrollLeft = arrastre.current.left - (e.clientX - arrastre.current.x);
    caja.current.scrollTop = arrastre.current.top - (e.clientY - arrastre.current.y);
  };
  const terminar = () => (arrastre.current = null);
  const rueda = (e) => {
    if (!e.ctrlKey) return;
    e.preventDefault();
    onZoom((z) => Math.min(800, Math.max(25, Math.round(z * (e.deltaY < 0 ? 1.15 : 1 / 1.15)))));
  };
  useEffect(() => {
    const c = caja.current;
    c?.addEventListener("wheel", rueda, { passive: false });
    return () => c?.removeEventListener("wheel", rueda);
  });

  const cargando = archivoId && imagen.clave !== clave;

  return (
    <div className="flex-1 min-w-0 flex flex-col gap-space-sm">
      <div className="flex items-center gap-2">
        <select
          value={archivoId || ""}
          onChange={(e) => {
            setPagina(1);
            onArchivo(e.target.value);
          }}
          className={claseSelect}
        >
          {archivos.map((a) => (
            <option key={a.id} value={a.id}>
              {a.rol_grafotecnico === "dubitado" ? "[D] " : a.rol_grafotecnico === "indubitado" ? "[I] " : ""}
              {a.nombre_original}
            </option>
          ))}
        </select>
        {imagen.paginas > 1 && (
          <div className="flex items-center gap-1 font-label-code-sm text-label-code-sm text-on-surface-variant">
            <button disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)} className="disabled:opacity-40">
              <span className="material-symbols-outlined text-base">chevron_left</span>
            </button>
            {pagina}/{imagen.paginas}
            <button disabled={pagina >= imagen.paginas} onClick={() => setPagina(pagina + 1)} className="disabled:opacity-40">
              <span className="material-symbols-outlined text-base">chevron_right</span>
            </button>
          </div>
        )}
      </div>
      <div className="flex items-center gap-2 min-h-6">
        {archivo?.rol_grafotecnico ? <InsigniaRol rol={archivo.rol_grafotecnico} /> : (
          <span className="font-label-ui text-label-ui text-outline">Sin clasificar</span>
        )}
      </div>
      <div
        ref={caja}
        onScroll={alDesplazar}
        onMouseDown={empezar}
        onMouseMove={mover}
        onMouseUp={terminar}
        onMouseLeave={terminar}
        className="h-[28rem] overflow-auto rounded-lg bg-white border border-outline-variant/40 cursor-grab active:cursor-grabbing select-none"
      >
        {cargando ? (
          <p className="p-space-md font-body-sm text-body-sm text-neutral-500">Cargando página…</p>
        ) : imagen.error ? (
          <p className="p-space-md font-body-sm text-body-sm text-error">{imagen.error}</p>
        ) : imagen.url ? (
          <img
            src={imagen.url}
            alt={archivo?.nombre_original || "Documento"}
            draggable={false}
            style={{ width: `${zoom}%`, maxWidth: "none" }}
            className="block"
          />
        ) : null}
      </div>
    </div>
  );
}

export default function CotejoGrafotecnico({ archivos }) {
  const visibles = archivos.filter((a) => a.estado_procesamiento === "listo" && esVisualizable(a));
  const primero = (rol) => visibles.find((a) => a.rol_grafotecnico === rol)?.id;
  const [izquierda, setIzquierda] = useState(null);
  const [derecha, setDerecha] = useState(null);
  const [zoom, setZoom] = useState(100);
  const [sincronizar, setSincronizar] = useState(true);
  const [scroll, setScroll] = useState({ izq: null, der: null });

  if (visibles.length === 0) return null;
  // Por defecto: dubitado a la izquierda, indubitado a la derecha.
  const idIzq = izquierda || primero("dubitado") || visibles[0].id;
  const idDer = derecha || primero("indubitado") || visibles[Math.min(1, visibles.length - 1)].id;

  const desplazar = (lado) => (pos) => {
    if (sincronizar) setScroll(lado === "izq" ? { izq: null, der: pos } : { izq: pos, der: null });
  };

  return (
    <div className="bg-surface-container-low rounded-xl p-space-md mb-space-md flex flex-col gap-space-sm">
      <div className="flex items-center justify-between gap-space-sm flex-wrap">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary">compare</span>
          <h2 className="font-headline-sm text-headline-sm text-on-surface">Cotejo grafotécnico</h2>
        </div>
        <div className="flex items-center gap-space-md flex-wrap font-body-sm text-body-sm text-on-surface-variant">
          <label className="flex items-center gap-2">
            <span className="material-symbols-outlined text-base">zoom_in</span>
            <input type="range" min={25} max={800} step={5} value={zoom} onChange={(e) => setZoom(Number(e.target.value))} className="accent-primary" />
            <span className="font-label-code-sm text-label-code-sm w-12">{zoom}%</span>
          </label>
          <button onClick={() => setZoom(100)} className="text-primary hover:underline">Ajustar</button>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input type="checkbox" checked={sincronizar} onChange={(e) => setSincronizar(e.target.checked)} className="accent-primary" />
            Mover ambos a la vez
          </label>
        </div>
      </div>
      <p className="font-body-sm text-body-sm text-outline">
        Arrastra para moverte por el documento y usa Ctrl + rueda del mouse para acercar. Con "Mover ambos a la vez",
        las dos vistas van al mismo punto para comparar el mismo trazo.
      </p>
      <div className="flex flex-col lg:flex-row gap-space-md">
        <Visor archivos={visibles} archivoId={idIzq} onArchivo={setIzquierda} zoom={zoom} onZoom={setZoom} scroll={scroll.izq} onScroll={desplazar("izq")} />
        <Visor archivos={visibles} archivoId={idDer} onArchivo={setDerecha} zoom={zoom} onZoom={setZoom} scroll={scroll.der} onScroll={desplazar("der")} />
      </div>
    </div>
  );
}
