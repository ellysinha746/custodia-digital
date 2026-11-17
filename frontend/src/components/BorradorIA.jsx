import { useCallback, useEffect, useState } from "react";
import api from "../api";
import { useToast } from "./Toast";
import { puede, useUsuario } from "../permisos";

// Sprint 7 (historia 34): borrador DESCRIPTIVO del cotejo grafotécnico redactado con IA.
// Es apoyo, no dictamen: el perito lo revisa, lo corrige y lo firma.

const claseCampo =
  "w-full px-2.5 py-1.5 rounded-md bg-surface-container-lowest text-on-surface font-body-sm text-body-sm border border-outline-variant/40 focus:outline-none focus:ring-1 focus:ring-primary/50";

function fecha(f) {
  return new Date(f).toLocaleString("es-PE", { dateStyle: "medium", timeStyle: "short" });
}

async function bajar(id) {
  const { data } = await api.get(`/borradores-ia/${id}/descargar`, { responseType: "blob" });
  const url = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = url;
  a.download = `borrador_ia_${id.slice(0, 8)}.txt`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function Borrador({ b, esMio, onCambio }) {
  const { notificar } = useToast();
  const [abierto, setAbierto] = useState(b.estado === "borrador" && esMio);
  const [texto, setTexto] = useState(b.texto);
  const [firma, setFirma] = useState("");
  const [revisado, setRevisado] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const editable = b.estado === "borrador" && esMio;
  const sinGuardar = texto !== b.texto;

  const guardar = async () => {
    setGuardando(true);
    try {
      await api.patch(`/borradores-ia/${b.id}`, { texto });
      notificar("Cambios guardados.", { tipo: "success" });
      onCambio();
    } catch (err) {
      notificar(err.response?.data?.detail || "No se pudo guardar.", { tipo: "error" });
    } finally {
      setGuardando(false);
    }
  };

  const firmar = async (e) => {
    e.preventDefault();
    setGuardando(true);
    try {
      if (sinGuardar) await api.patch(`/borradores-ia/${b.id}`, { texto });
      await api.post(`/borradores-ia/${b.id}/firmar`, { firma, revisado });
      notificar("Borrador revisado y firmado.", { tipo: "success" });
      onCambio();
    } catch (err) {
      notificar(err.response?.data?.detail || "No se pudo firmar.", { tipo: "error" });
    } finally {
      setGuardando(false);
    }
  };

  const insignia =
    b.estado === "firmado"
      ? b.integro
        ? { texto: "Revisado y firmado", clase: "bg-tertiary/10 text-tertiary", icono: "verified" }
        : { texto: "Firmado · NO coincide", clase: "bg-error/10 text-error", icono: "gpp_bad" }
      : { texto: "Borrador sin firmar", clase: "bg-amber-400/10 text-amber-400", icono: "edit_note" };

  return (
    <div className="border border-outline-variant/30 rounded-lg p-space-sm flex flex-col gap-space-sm">
      <div className="flex items-center gap-2 flex-wrap font-body-sm text-body-sm">
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded font-label-ui text-label-ui ${insignia.clase}`}>
          <span className="material-symbols-outlined text-sm">{insignia.icono}</span>
          {insignia.texto}
        </span>
        {b.editado && <span className="px-2 py-0.5 rounded bg-surface-container-high text-on-surface-variant font-label-ui text-label-ui">Corregido por el perito</span>}
        <span className="text-on-surface-variant">{fecha(b.generado_en)} · {b.generado_por}</span>
        <span className="text-outline font-label-code-sm text-label-code-sm">· {b.modelo_respondio || b.modelo_solicitado}</span>
        <div className="ml-auto flex items-center gap-space-md">
          <button onClick={() => setAbierto(!abierto)} className="font-label-ui text-label-ui text-primary hover:underline">
            {abierto ? "Ocultar" : editable ? "Revisar" : "Ver"}
          </button>
          <button
            onClick={() => bajar(b.id).catch(() => notificar("No se pudo descargar.", { tipo: "error" }))}
            className="inline-flex items-center gap-1 font-label-ui text-label-ui text-primary hover:underline"
          >
            <span className="material-symbols-outlined text-base">download</span>.txt
          </button>
        </div>
      </div>
      <p className="font-label-code-sm text-label-code-sm text-outline">
        Enviado a {b.enviado.proveedor}: {b.enviado.imagenes} imagen(es), {b.enviado.textos_ocr} texto(s) OCR
        {b.enviado.metricas ? `, ${b.enviado.metricas} conjunto(s) de métricas` : ""} ·{" "}
        {b.documentos.map((d) => `${d.etiqueta} ${d.nombre}`).join(" · ")}
      </p>
      {b.estado === "firmado" && (
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          Firmado por <strong>{b.firmado_por}</strong> el {fecha(b.firmado_en)} · SHA-256 {b.hash_texto?.slice(0, 16)}…
        </p>
      )}

      {abierto && (
        <>
          {editable ? (
            <textarea value={texto} onChange={(e) => setTexto(e.target.value)} rows={18} className={`${claseCampo} font-label-code-sm text-label-code-sm leading-relaxed`} />
          ) : (
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-md bg-surface-container-lowest p-space-sm font-label-code-sm text-label-code-sm text-on-surface">
              {b.texto}
            </pre>
          )}
          {editable && (
            <form onSubmit={firmar} className="flex flex-col gap-space-sm">
              <div className="flex justify-end">
                <button type="button" onClick={guardar} disabled={!sinGuardar || guardando} className="px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface font-label-ui text-label-ui disabled:opacity-50">
                  Guardar cambios
                </button>
              </div>
              <div className="rounded-lg border border-outline-variant/40 p-space-sm flex flex-col gap-space-sm">
                <label className="flex items-start gap-2 font-body-sm text-body-sm text-on-surface cursor-pointer">
                  <input type="checkbox" checked={revisado} onChange={(e) => setRevisado(e.target.checked)} className="mt-1 accent-primary" />
                  Revisé el borrador contra los documentos y corregí lo necesario. Entiendo que la IA solo describe y que la
                  conclusión pericial es mía.
                </label>
                <div className="flex gap-space-sm flex-wrap">
                  <input required value={firma} onChange={(e) => setFirma(e.target.value)} placeholder="Escribe tu nombre completo para firmar" className={`${claseCampo} flex-1 min-w-56`} />
                  <button type="submit" disabled={!revisado || firma.trim().length < 3 || guardando} className="px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui disabled:opacity-60">
                    Firmar como revisado
                  </button>
                </div>
              </div>
            </form>
          )}
        </>
      )}
    </div>
  );
}

export default function BorradorIA({ caso, archivos }) {
  const { notificar } = useToast();
  const usuario = useUsuario();
  const [estadoIA, setEstadoIA] = useState(null);
  const [borradores, setBorradores] = useState([]);
  const [confirmando, setConfirmando] = useState(false);
  const [generando, setGenerando] = useState(false);

  const cargar = useCallback(async () => {
    try {
      const [{ data: e }, { data: l }] = await Promise.all([api.get("/ia/estado"), api.get(`/casos/${caso.id}/borradores-ia`)]);
      setEstadoIA(e);
      setBorradores(l);
    } catch {
      setBorradores([]);
    }
  }, [caso.id]);

  useEffect(() => {
    let vigente = true;
    Promise.all([api.get("/ia/estado"), api.get(`/casos/${caso.id}/borradores-ia`)])
      .then(([{ data: e }, { data: l }]) => {
        if (vigente) {
          setEstadoIA(e);
          setBorradores(l);
        }
      })
      .catch(() => {});
    return () => {
      vigente = false;
    };
  }, [caso.id]);

  const dubitados = archivos.filter((a) => a.rol_grafotecnico === "dubitado").length;
  const indubitados = archivos.filter((a) => a.rol_grafotecnico === "indubitado").length;
  const puedeGenerar = puede(usuario, "editar_metadatos") && caso.estado !== "cerrado";
  const listos = dubitados > 0 && indubitados > 0;

  const generar = async () => {
    setGenerando(true);
    setConfirmando(false);
    try {
      await api.post(`/casos/${caso.id}/borradores-ia`, null, { timeout: 240000 });
      notificar("Borrador generado. Revísalo antes de firmarlo.", { tipo: "success" });
      cargar();
    } catch (err) {
      notificar(err.response?.data?.detail || "No se pudo generar el borrador.", { tipo: "error" });
      cargar();
    } finally {
      setGenerando(false);
    }
  };

  return (
    <div className="bg-surface-container-low rounded-xl p-space-md mb-space-md flex flex-col gap-space-sm">
      <div className="flex items-center justify-between gap-space-sm flex-wrap">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary">auto_awesome</span>
          <h2 className="font-headline-sm text-headline-sm text-on-surface">Borrador descriptivo asistido por IA</h2>
        </div>
        {puedeGenerar && !confirmando && (
          <button
            onClick={() => setConfirmando(true)}
            disabled={!estadoIA?.habilitada || !listos || generando}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui disabled:opacity-50"
          >
            <span className="material-symbols-outlined text-base">{generando ? "progress_activity" : "edit_document"}</span>
            {generando ? "Redactando… (puede tardar un minuto)" : "Generar borrador"}
          </button>
        )}
      </div>
      <p className="font-body-sm text-body-sm text-on-surface-variant">
        La IA describe lo observable en los documentos dubitados e indubitados y propone puntos a verificar.
        <strong> Nunca dictamina autenticidad:</strong> la conclusión la escribe y firma el perito.
      </p>
      {estadoIA && !estadoIA.habilitada && (
        <p className="font-body-sm text-body-sm text-outline">
          La IA no está configurada en este servidor (falta ANTHROPIC_API_KEY): ningún documento sale del laboratorio.
        </p>
      )}
      {estadoIA?.habilitada && !listos && (
        <p className="font-body-sm text-body-sm text-outline">
          Clasifica al menos un documento como dubitado y otro como indubitado ({dubitados} y {indubitados} ahora).
        </p>
      )}
      {confirmando && (
        <div className="rounded-lg border border-amber-400/40 bg-amber-400/10 p-space-sm flex flex-col gap-space-sm">
          <p className="font-body-sm text-body-sm text-on-surface">
            Se enviarán a <strong>{estadoIA.proveedor}</strong> ({estadoIA.modelo}) la primera página de{" "}
            {dubitados + indubitados} documento(s) como imagen, su texto OCR y las métricas disponibles. Las firmas son datos
            personales (Ley 29733): queda registrado en la cadena de custodia de cada documento.
          </p>
          <div className="flex gap-space-sm justify-end">
            <button onClick={() => setConfirmando(false)} className="px-3 py-1.5 rounded-lg font-label-ui text-label-ui text-on-surface-variant hover:bg-surface-container">
              Cancelar
            </button>
            <button onClick={generar} className="px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui">
              Enviar y generar
            </button>
          </div>
        </div>
      )}
      {borradores.map((b) => (
        <Borrador key={b.id} b={b} esMio={usuario?.id === b.generado_por_id || usuario?.rol === "admin"} onCambio={cargar} />
      ))}
    </div>
  );
}
