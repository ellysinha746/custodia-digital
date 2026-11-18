import { useEffect, useRef, useState } from "react";
import api from "../api";
import { useToast } from "./Toast";
import { puede, useUsuario } from "../permisos";
import { esVisualizable } from "../grafotecnia";

// Sprint 7 (historia 30): análisis comparativo de firmas con OpenCV.
// Se elige UNA firma dubitada y DOS o más indubitadas; en cada una se puede marcar con el
// mouse el rectángulo donde está la firma. El servidor mide cuánto varían los patrones entre
// sí (variación natural del autor) y si la dubitada cae dentro. Apoya al perito: no dictamina.

const ESTADOS = {
  dentro: { texto: "Dentro del rango", clase: "bg-tertiary/10 text-tertiary border-tertiary/30" },
  limite: { texto: "En el límite", clase: "bg-amber-400/10 text-amber-500 border-amber-400/40" },
  fuera: { texto: "Fuera del rango", clase: "bg-error/10 text-error border-error/30" },
};

function fecha(f) {
  return new Date(f).toLocaleString("es-PE", { dateStyle: "medium", timeStyle: "short" });
}

function numero(v, formato) {
  return formato === "porcentaje" ? `${Math.round(v * 100)} %` : v.toFixed(3);
}

// ------------------------------------------------------------ recorte con el mouse

function Recortador({ archivo, valor, onCambio, onCerrar }) {
  const [pagina, setPagina] = useState(valor?.pagina || 1);
  const [imagen, setImagen] = useState({ clave: null, url: null, paginas: 1, error: null });
  const clave = `${archivo.id}|${pagina}`;
  const [rect, setRect] = useState(valor?.recorte || null);
  const marco = useRef(null);
  const inicio = useRef(null);

  useEffect(() => {
    let vigente = true;
    let url = null;
    api
      .get(`/archivos/${archivo.id}/vista`, { params: { pagina }, responseType: "blob" })
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
  }, [archivo.id, pagina, clave]);
  const cargando = imagen.clave !== clave;

  const punto = (e) => {
    const r = marco.current.getBoundingClientRect();
    return {
      x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)),
      y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)),
    };
  };
  const bajar = (e) => {
    e.preventDefault();
    inicio.current = punto(e);
    setRect(null);
  };
  const mover = (e) => {
    if (!inicio.current) return;
    const p = punto(e);
    const a = inicio.current;
    setRect({ x: Math.min(a.x, p.x), y: Math.min(a.y, p.y), ancho: Math.abs(p.x - a.x), alto: Math.abs(p.y - a.y) });
  };
  const soltar = () => {
    inicio.current = null;
    setRect((r) => (r && (r.ancho < 0.02 || r.alto < 0.02) ? null : r));
  };

  const redondear = (r) => r && Object.fromEntries(Object.entries(r).map(([k, v]) => [k, Math.round(v * 10000) / 10000]));

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-space-md" onClick={onCerrar}>
      <div
        className="bg-surface-container-low rounded-xl p-space-md w-full max-w-4xl max-h-[92vh] flex flex-col gap-space-sm"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-2">
          <h3 className="font-headline-sm text-headline-sm text-on-surface truncate">Ubicar la firma — {archivo.nombre_original}</h3>
          {imagen.paginas > 1 && (
            <div className="flex items-center gap-1 font-label-code-sm text-label-code-sm text-on-surface-variant">
              <button disabled={pagina <= 1} onClick={() => { setPagina(pagina - 1); setRect(null); }} className="disabled:opacity-40">
                <span className="material-symbols-outlined text-base">chevron_left</span>
              </button>
              Página {pagina}/{imagen.paginas}
              <button disabled={pagina >= imagen.paginas} onClick={() => { setPagina(pagina + 1); setRect(null); }} className="disabled:opacity-40">
                <span className="material-symbols-outlined text-base">chevron_right</span>
              </button>
            </div>
          )}
        </div>
        <p className="font-body-sm text-body-sm text-outline">
          Arrastra el mouse para encerrar solo la firma (sin sellos, líneas ni texto impreso). Sin rectángulo se usa la página completa.
        </p>
        <div className="flex-1 min-h-0 overflow-auto rounded-lg bg-white border border-outline-variant/40 flex items-start justify-center">
          {cargando ? (
            <p className="p-space-md font-body-sm text-body-sm text-neutral-500">Cargando página…</p>
          ) : imagen.error ? (
            <p className="p-space-md font-body-sm text-body-sm text-error">{imagen.error}</p>
          ) : (
            <div
              ref={marco}
              className="relative cursor-crosshair select-none"
              onMouseDown={bajar}
              onMouseMove={mover}
              onMouseUp={soltar}
              onMouseLeave={soltar}
            >
              <img src={imagen.url} alt={archivo.nombre_original} draggable={false} className="block max-h-[64vh] w-auto" />
              {rect && (
                <div
                  className="absolute border-2 border-primary bg-primary/10 pointer-events-none"
                  style={{ left: `${rect.x * 100}%`, top: `${rect.y * 100}%`, width: `${rect.ancho * 100}%`, height: `${rect.alto * 100}%` }}
                />
              )}
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2">
          <button onClick={() => setRect(null)} className="px-3 py-1.5 rounded-md font-label-ui text-label-ui text-on-surface-variant hover:bg-surface-container-high">
            Página completa
          </button>
          <button onClick={onCerrar} className="px-3 py-1.5 rounded-md font-label-ui text-label-ui text-on-surface-variant hover:bg-surface-container-high">
            Cancelar
          </button>
          <button
            onClick={() => { onCambio({ pagina, recorte: redondear(rect) }); onCerrar(); }}
            className="px-3 py-1.5 rounded-md bg-primary text-on-primary font-label-ui text-label-ui"
          >
            Usar esta zona
          </button>
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------ resultado

function Resultado({ a }) {
  const r = a.resultado;
  const nombres = Object.fromEntries(r.firmas.map((f) => [f.id, f.nombre]));
  return (
    <div className="flex flex-col gap-space-md">
      {r.avisos?.map((t) => (
        <p key={t} className="px-3 py-2 rounded-md bg-amber-400/10 border border-amber-400/40 font-body-sm text-body-sm text-on-surface">
          <span className="material-symbols-outlined text-base align-middle mr-1 text-amber-500">warning</span>{t}
        </p>
      ))}

      <div className="flex gap-space-sm flex-wrap">
        {r.firmas.map((f) => (
          <figure key={f.id} className="bg-white rounded-md border border-outline-variant/40 p-2 w-44">
            <img src={`data:image/png;base64,${f.miniatura_png}`} alt={f.nombre} className="h-16 w-full object-contain" />
            <figcaption className="mt-1 font-label-ui text-label-ui text-neutral-700 truncate" title={f.nombre}>
              <span className={f.rol === "dubitado" ? "text-error" : "text-tertiary"}>{f.rol === "dubitado" ? "[D] " : "[I] "}</span>
              {f.nombre}
            </figcaption>
            <p className="font-label-code-sm text-label-code-sm text-neutral-500">
              incl. {f.medidas.inclinacion}° · trazos {f.medidas.trazos}
            </p>
          </figure>
        ))}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full font-body-sm text-body-sm text-on-surface">
          <thead>
            <tr className="text-left text-on-surface-variant border-b border-outline-variant/30">
              <th className="py-2 pr-3 font-label-ui text-label-ui">Métrica</th>
              <th className="py-2 pr-3 font-label-ui text-label-ui">Dubitada vs patrones (promedio)</th>
              <th className="py-2 pr-3 font-label-ui text-label-ui">Variación natural del autor</th>
              <th className="py-2 font-label-ui text-label-ui">Resultado</th>
            </tr>
          </thead>
          <tbody>
            {r.resumen.map((m) => (
              <tr key={m.clave} className="border-b border-outline-variant/15">
                <td className="py-2 pr-3">
                  {m.etiqueta}
                  <span className="block font-label-ui text-label-ui text-outline">
                    {m.mayor_es_mas_parecido ? "más alto = más parecido" : "más bajo = más parecido"}
                  </span>
                </td>
                <td className="py-2 pr-3 font-label-code-sm text-label-code-sm">{numero(m.dubitada_promedio, m.formato)}</td>
                <td className="py-2 pr-3 font-label-code-sm text-label-code-sm">
                  {numero(m.rango_autor.min, m.formato)} – {numero(m.rango_autor.max, m.formato)}
                </td>
                <td className="py-2">
                  <span className={`px-2 py-0.5 rounded-full border font-label-ui text-label-ui ${ESTADOS[m.estado].clase}`}>
                    {ESTADOS[m.estado].texto}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div>
        <p className="font-label-ui text-label-ui text-on-surface-variant mb-2">
          Superposición:{" "}
          <span className="inline-block w-3 h-3 rounded-sm bg-black border border-white/60 align-middle" /> coinciden ·{" "}
          <span className="inline-block w-3 h-3 rounded-sm bg-blue-600 align-middle" /> solo en la dubitada ·{" "}
          <span className="inline-block w-3 h-3 rounded-sm bg-orange-500 align-middle" /> solo en el patrón
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-space-sm">
          {r.comparaciones.map((c) => (
            <figure key={c.indubitada_id} className="bg-white rounded-md border border-outline-variant/40 p-2">
              {c.superposicion_png && (
                <img src={`data:image/png;base64,${c.superposicion_png}`} alt={`Superposición con ${c.indubitada}`} className="w-full h-32 object-contain" />
              )}
              <figcaption className="mt-1 font-label-code-sm text-label-code-sm text-neutral-600">
                vs {nombres[c.indubitada_id] || c.indubitada} · superposición {Math.round(c.valores.superposicion * 100)} % · ORB{" "}
                {Math.round(c.valores.puntos_coincidentes * 100)} % · forma {c.valores.diferencia_forma.toFixed(3)}
              </figcaption>
            </figure>
          ))}
        </div>
      </div>

      <p className="font-body-sm text-body-sm text-on-surface-variant">{r.nota}</p>
      <p className="font-label-code-sm text-label-code-sm text-outline break-all">
        {r.motor} · {a.realizado_por} · {fecha(a.realizado_en)} · SHA-256 del resultado {a.hash_resultado}{" "}
        {a.integro ? (
          <span className="text-tertiary">(íntegro)</span>
        ) : (
          <span className="text-error">(NO COINCIDE: el resultado guardado fue alterado)</span>
        )}
      </p>
    </div>
  );
}

// ------------------------------------------------------------ componente principal

export default function AnalisisFirmas({ caso, archivos }) {
  const { notificar } = useToast();
  const usuario = useUsuario();
  const listos = archivos.filter((a) => a.estado_procesamiento === "listo" && esVisualizable(a));
  const dubitados = listos.filter((a) => a.rol_grafotecnico === "dubitado");
  const indubitados = listos.filter((a) => a.rol_grafotecnico === "indubitado");

  const [dubitada, setDubitada] = useState(null);
  const [patrones, setPatrones] = useState(null); // null = todos los indubitados
  const [zonas, setZonas] = useState({}); // archivo_id -> {pagina, recorte}
  const [recortando, setRecortando] = useState(null);
  const [analizando, setAnalizando] = useState(false);
  const [historial, setHistorial] = useState([]);
  const [visible, setVisible] = useState(null);

  const idDub = dubitada || dubitados[0]?.id;
  const idsPatrones = patrones || indubitados.map((a) => a.id);
  const puedeAnalizar = puede(usuario, "editar_metadatos") && caso.estado !== "cerrado";

  useEffect(() => {
    let vigente = true;
    api
      .get(`/casos/${caso.id}/firmas/analisis`)
      .then(({ data }) => vigente && setHistorial(data))
      .catch(() => {}); // sin historial visible
    return () => {
      vigente = false;
    };
  }, [caso.id]);

  const alternar = (id) => setPatrones(idsPatrones.includes(id) ? idsPatrones.filter((x) => x !== id) : [...idsPatrones, id]);
  const entrada = (id) => ({ archivo_id: id, pagina: zonas[id]?.pagina || 1, recorte: zonas[id]?.recorte || null });

  const analizar = async () => {
    setAnalizando(true);
    try {
      const { data } = await api.post(`/casos/${caso.id}/firmas/analisis`, {
        dubitada: entrada(idDub),
        indubitadas: idsPatrones.map(entrada),
      });
      setHistorial((h) => [data, ...h]);
      setVisible(data.id);
      const r = data.resultado;
      notificar(`Análisis listo: ${r.metricas_fuera_de_rango} de ${r.resumen.length} métricas fuera del rango del autor.`, { tipo: "success" });
    } catch (err) {
      const d = err.response?.data?.detail;
      notificar(typeof d === "string" ? d : "No se pudo analizar las firmas.", { tipo: "error" });
    } finally {
      setAnalizando(false);
    }
  };

  if (dubitados.length === 0 && indubitados.length === 0 && historial.length === 0) return null;

  const zonaTexto = (id) => {
    const z = zonas[id];
    if (!z?.recorte) return z?.pagina > 1 ? `pág. ${z.pagina}, completa` : "página completa";
    return `pág. ${z.pagina}, zona marcada`;
  };
  const BotonZona = ({ a }) =>
    puedeAnalizar && (
      <button
        onClick={(e) => {
          e.preventDefault(); // está dentro de un <label>: que no cambie la selección
          setRecortando(a);
        }}
        className="ml-auto flex items-center gap-1 text-primary font-label-ui text-label-ui hover:underline">
        <span className="material-symbols-outlined text-base">crop</span>
        {zonaTexto(a.id)}
      </button>
    );

  const actual = historial.find((h) => h.id === visible);

  return (
    <div className="bg-surface-container-low rounded-xl p-space-md mb-space-md flex flex-col gap-space-md">
      <div className="flex items-center gap-2">
        <span className="material-symbols-outlined text-primary">draw</span>
        <h2 className="font-headline-sm text-headline-sm text-on-surface">Análisis de firmas</h2>
        <span className="font-label-code-sm text-label-code-sm text-outline">OpenCV · apoyo al perito</span>
      </div>

      {puedeAnalizar && (
        <>
          {dubitados.length === 0 || indubitados.length < 2 ? (
            <p className="font-body-sm text-body-sm text-on-surface-variant">
              Para analizar, marca en "Archivos del caso" al menos <b>1 documento dubitado</b> y <b>2 indubitados</b> (mejor 3 o más)
              que sean imágenes o PDF.
            </p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-space-md">
              <div>
                <p className="font-label-ui text-label-ui text-error mb-1">Firma dubitada (1)</p>
                {dubitados.map((a) => (
                  <label key={a.id} className="flex items-center gap-2 py-1 font-body-sm text-body-sm text-on-surface">
                    <input type="radio" name="dubitada" checked={idDub === a.id} onChange={() => setDubitada(a.id)} className="accent-primary" />
                    <span className="truncate">{a.nombre_original}</span>
                    {idDub === a.id && <BotonZona a={a} />}
                  </label>
                ))}
              </div>
              <div>
                <p className="font-label-ui text-label-ui text-tertiary mb-1">Patrones indubitados (2 o más)</p>
                {indubitados.map((a) => (
                  <label key={a.id} className="flex items-center gap-2 py-1 font-body-sm text-body-sm text-on-surface">
                    <input type="checkbox" checked={idsPatrones.includes(a.id)} onChange={() => alternar(a.id)} className="accent-primary" />
                    <span className="truncate">{a.nombre_original}</span>
                    {idsPatrones.includes(a.id) && <BotonZona a={a} />}
                  </label>
                ))}
              </div>
            </div>
          )}
          {dubitados.length > 0 && indubitados.length >= 2 && (
            <div className="flex items-center gap-space-sm flex-wrap">
              <button
                onClick={analizar}
                disabled={analizando || idsPatrones.length < 2}
                className="px-4 py-2 rounded-md bg-primary text-on-primary font-label-ui text-label-ui disabled:opacity-50 flex items-center gap-2"
              >
                <span className="material-symbols-outlined text-base">{analizando ? "hourglass_top" : "analytics"}</span>
                {analizando ? "Analizando…" : "Analizar firmas"}
              </button>
              {idsPatrones.length < 2 && <span className="font-body-sm text-body-sm text-error">Elige al menos 2 patrones.</span>}
            </div>
          )}
        </>
      )}

      {historial.length > 0 && (
        <div className="flex flex-col gap-1">
          <p className="font-label-ui text-label-ui text-on-surface-variant">Análisis realizados</p>
          {historial.map((h) => (
            <button
              key={h.id}
              onClick={() => setVisible(visible === h.id ? null : h.id)}
              className={`text-left px-3 py-2 rounded-md font-body-sm text-body-sm flex items-center gap-2 ${
                visible === h.id ? "bg-surface-container-high" : "hover:bg-surface-container-high/60"
              }`}
            >
              <span className="material-symbols-outlined text-base text-outline">{visible === h.id ? "expand_less" : "expand_more"}</span>
              <span className="text-on-surface">{fecha(h.realizado_en)}</span>
              <span className="text-on-surface-variant truncate">· {h.realizado_por} · {h.entradas[0]?.nombre} vs {h.entradas.length - 1} patrón(es)</span>
              <span className="ml-auto font-label-code-sm text-label-code-sm text-error whitespace-nowrap">
                {h.resultado.metricas_fuera_de_rango}/{h.resultado.resumen.length} fuera
              </span>
            </button>
          ))}
        </div>
      )}

      {actual && <Resultado a={actual} />}

      {recortando && (
        <Recortador
          archivo={recortando}
          valor={zonas[recortando.id]}
          onCambio={(z) => setZonas({ ...zonas, [recortando.id]: z })}
          onCerrar={() => setRecortando(null)}
        />
      )}
    </div>
  );
}
