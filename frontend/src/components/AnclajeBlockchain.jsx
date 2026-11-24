import { useEffect, useState } from "react";
import api from "../api";
import { useToast } from "./Toast";
import { puede, useUsuario } from "../permisos";

// Sprint 8 (historia 39): anclaje del historial de custodia en Bitcoin con OpenTimestamps.
// Solo viaja la HUELLA (SHA-256) del historial: ningún dato del caso sale del laboratorio.

function fecha(f) {
  return new Date(f).toLocaleString("es-PE", { dateStyle: "medium", timeStyle: "short" });
}

async function descargar(url, nombre) {
  const { data } = await api.get(url, { responseType: "blob" });
  const enlace = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = enlace;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(enlace);
}

function Estado({ a }) {
  if (a.estado === "confirmado") {
    return (
      <a
        href={`https://mempool.space/block/${a.bloque_bitcoin}`}
        target="_blank"
        rel="noreferrer noopener"
        className="px-2 py-0.5 rounded-full border border-tertiary/30 bg-tertiary/10 text-tertiary font-label-ui text-label-ui hover:underline"
        title="Ver el bloque en un explorador público de Bitcoin"
      >
        Confirmado · bloque #{a.bloque_bitcoin}
      </a>
    );
  }
  return (
    <span
      className="px-2 py-0.5 rounded-full border border-amber-400/40 bg-amber-400/10 text-amber-500 font-label-ui text-label-ui"
      title="Los calendarios ya recibieron la huella; Bitcoin la incluye en un bloque en unas horas."
    >
      Pendiente · esperando bloque
    </span>
  );
}

export default function AnclajeBlockchain() {
  const usuario = useUsuario();
  const { notificar } = useToast();
  const [anclajes, setAnclajes] = useState([]);
  const [ocupado, setOcupado] = useState(null); // "anclar" | id del anclaje en curso
  const [verificaciones, setVerificaciones] = useState({});
  const puedeAnclar = puede(usuario, "anclar_blockchain");

  useEffect(() => {
    let vigente = true;
    api
      .get("/blockchain/anclajes")
      .then(({ data }) => vigente && setAnclajes(data))
      .catch(() => {}); // sin permiso o sin datos: la tarjeta queda vacía
    return () => {
      vigente = false;
    };
  }, []);

  const error = (err, texto) => {
    const d = err.response?.data?.detail;
    notificar(typeof d === "string" ? d : texto, { tipo: "error" });
  };

  const anclar = async () => {
    setOcupado("anclar");
    try {
      const { data } = await api.post("/blockchain/anclajes");
      setAnclajes((l) => [data, ...l]);
      notificar(`Se anclaron ${data.total_registros} registros de custodia. Bitcoin lo confirmará en unas horas.`, { tipo: "success" });
    } catch (err) {
      error(err, "No se pudo anclar el historial.");
    } finally {
      setOcupado(null);
    }
  };

  const actualizar = async (a) => {
    setOcupado(a.id);
    try {
      const { data } = await api.post(`/blockchain/anclajes/${a.id}/actualizar`);
      setAnclajes((l) => l.map((x) => (x.id === a.id ? data : x)));
      notificar(
        data.estado === "confirmado" ? `Confirmado en el bloque #${data.bloque_bitcoin} de Bitcoin.` : "Todavía pendiente: vuelve a consultar en unas horas.",
        { tipo: data.estado === "confirmado" ? "success" : "info" },
      );
    } catch (err) {
      error(err, "No se pudo consultar el estado.");
    } finally {
      setOcupado(null);
    }
  };

  const verificar = async (a) => {
    setOcupado(a.id);
    try {
      const { data } = await api.get(`/blockchain/anclajes/${a.id}/verificar`);
      setVerificaciones((v) => ({ ...v, [a.id]: data }));
    } catch (err) {
      error(err, "No se pudo verificar.");
    } finally {
      setOcupado(null);
    }
  };

  const nombre = (a, ext) => `historial_custodia_${a.hasta.slice(0, 19).replace(/[-:]/g, "").replace("T", "_")}.${ext}`;

  if (!puede(usuario, "ver_blockchain")) return null;

  return (
    <div className="bg-surface-container-low rounded-xl p-space-md mb-space-lg flex flex-col gap-space-sm">
      <div className="flex items-start justify-between gap-space-md flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary">link</span>
            <h2 className="font-headline-sm text-headline-sm text-on-surface">Anclaje en blockchain</h2>
            <span className="font-label-code-sm text-label-code-sm text-outline">OpenTimestamps · Bitcoin</span>
          </div>
          <p className="font-body-sm text-body-sm text-on-surface-variant max-w-3xl mt-1">
            La huella SHA-256 de todo el historial de custodia se registra en Bitcoin. Desde ese momento nadie, ni el
            administrador, puede cambiar o borrar un registro anterior sin que la verificación lo detecte. Solo viaja la
            huella: ningún dato del caso sale del laboratorio. Se ancla solo una vez al día si hubo movimientos.
          </p>
        </div>
        {puedeAnclar && (
          <button
            onClick={anclar}
            disabled={ocupado === "anclar"}
            className="px-4 py-2 rounded-md bg-primary text-on-primary font-label-ui text-label-ui disabled:opacity-50 flex items-center gap-2"
          >
            <span className="material-symbols-outlined text-base">{ocupado === "anclar" ? "hourglass_top" : "anchor"}</span>
            {ocupado === "anclar" ? "Anclando…" : "Anclar historial ahora"}
          </button>
        )}
      </div>

      {anclajes.length === 0 ? (
        <p className="font-body-sm text-body-sm text-outline">Todavía no hay anclajes.</p>
      ) : (
        <div className="flex flex-col gap-1">
          {anclajes.map((a) => {
            const v = verificaciones[a.id];
            return (
              <div key={a.id} className="rounded-md bg-surface-container px-3 py-2 flex flex-col gap-1">
                <div className="flex items-center gap-space-sm flex-wrap font-body-sm text-body-sm">
                  <span className="text-on-surface">Hasta {fecha(a.hasta)}</span>
                  <span className="text-on-surface-variant">· {a.total_registros} registros</span>
                  <span className="text-on-surface-variant">· {a.creado_por || "automático"}</span>
                  <Estado a={a} />
                  <div className="ml-auto flex items-center gap-3 font-label-ui text-label-ui">
                    {puedeAnclar && a.estado === "pendiente" && (
                      <button onClick={() => actualizar(a)} disabled={ocupado === a.id} className="text-primary hover:underline disabled:opacity-50">
                        Consultar confirmación
                      </button>
                    )}
                    <button onClick={() => verificar(a)} disabled={ocupado === a.id} className="text-primary hover:underline disabled:opacity-50">
                      Verificar
                    </button>
                    <button
                      onClick={() => descargar(`/blockchain/anclajes/${a.id}/ots`, nombre(a, "txt.ots")).catch((e) => error(e, "No se pudo descargar."))}
                      className="text-primary hover:underline"
                    >
                      Prueba .ots
                    </button>
                    {puedeAnclar && (
                      <button
                        onClick={() => descargar(`/blockchain/anclajes/${a.id}/historial`, nombre(a, "txt")).catch((e) => error(e, "No se pudo descargar."))}
                        className="text-primary hover:underline"
                      >
                        Historial .txt
                      </button>
                    )}
                  </div>
                </div>
                <p className="font-label-code-sm text-label-code-sm text-outline break-all">huella SHA-256 {a.huella}</p>
                {v && (
                  <p className={`font-body-sm text-body-sm flex items-center gap-1 ${v.intacto ? "text-tertiary" : "text-error"}`}>
                    <span className="material-symbols-outlined text-base">{v.intacto ? "verified" : "gpp_bad"}</span>
                    {v.mensaje}
                  </p>
                )}
              </div>
            );
          })}
          <p className="font-label-ui text-label-ui text-outline mt-1">
            Verificación independiente: descarga el historial (.txt) y su prueba (.ots) y súbelos en opentimestamps.org.
          </p>
        </div>
      )}
    </div>
  );
}
