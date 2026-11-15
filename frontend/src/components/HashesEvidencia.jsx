import { useState } from "react";
import api from "../api";
import { useToast } from "./Toast";

// Sprint 6 (historia 23): doble hash (SHA-256 + SHA-1 + MD5) y cotejo con el informe de
// la herramienta forense con la que se hizo la extracción (Cellebrite, FTK Imager...).

const HERRAMIENTAS = [
  "Cellebrite UFED",
  "Cellebrite Physical Analyzer",
  "FTK Imager",
  "Magnet AXIOM",
  "Oxygen Forensic Detective",
  "EnCase",
  "X-Ways Forensics",
];

const ETIQUETA = { sha256: "SHA-256", sha1: "SHA-1", md5: "MD5" };

const RESULTADO = {
  coincide: { texto: "Coincide", icono: "verified", clase: "text-tertiary bg-tertiary/10 border-tertiary/30" },
  parcial: { texto: "Coincide en parte", icono: "rule", clase: "text-amber-400 bg-amber-400/10 border-amber-400/30" },
  no_coincide: { texto: "No coincide", icono: "gpp_bad", clase: "text-error bg-error/10 border-error/30" },
};

const claseCampo =
  "w-full px-2.5 py-1.5 rounded-md bg-surface-container-lowest text-on-surface font-body-sm text-body-sm border border-outline-variant/40 focus:outline-none focus:ring-1 focus:ring-primary/50";

function FilaHash({ etiqueta, valor }) {
  const { notificar } = useToast();
  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(valor);
      notificar(`${etiqueta} copiado.`, { tipo: "success" });
    } catch {
      notificar("No se pudo copiar: selecciona el texto a mano.", { tipo: "error" });
    }
  };
  return (
    <div className="grid grid-cols-[4.5rem_1fr_auto] items-start gap-2">
      <dt className="font-label-ui text-label-ui text-on-surface-variant pt-0.5">{etiqueta}</dt>
      <dd className="font-label-code-sm text-label-code-sm text-on-surface break-all">{valor || "—"}</dd>
      {valor && (
        <button onClick={copiar} title={`Copiar ${etiqueta}`} className="text-outline hover:text-primary">
          <span className="material-symbols-outlined text-base">content_copy</span>
        </button>
      )}
    </div>
  );
}

function InsigniaResultado({ resultado }) {
  const r = RESULTADO[resultado] || RESULTADO.no_coincide;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border font-label-ui text-label-ui ${r.clase}`}>
      <span className="material-symbols-outlined text-sm">{r.icono}</span>
      {r.texto}
    </span>
  );
}

export default function HashesEvidencia({ archivo, puedeCotejar, onCambio, onHistorial }) {
  const { notificar } = useToast();
  const [calculando, setCalculando] = useState(false);
  const [abierto, setAbierto] = useState(false);
  const [herramienta, setHerramienta] = useState(HERRAMIENTAS[0]);
  const [otraHerramienta, setOtraHerramienta] = useState("");
  const [referencia, setReferencia] = useState("");
  const [texto, setTexto] = useState("");
  const [cotejando, setCotejando] = useState(false);
  const [resultado, setResultado] = useState(null);

  const faltanAdicionales = !archivo.hash_sha1 || !archivo.hash_md5;
  const cotejos = [...(archivo.cotejos || [])].reverse();

  const calcular = async () => {
    setCalculando(true);
    try {
      await api.post(`/archivos/${archivo.id}/hashes-adicionales`);
      notificar("SHA-1 y MD5 calculados a partir del original.", { tipo: "success" });
      onCambio?.();
      onHistorial?.();
    } catch (err) {
      notificar(err.response?.data?.detail || "No se pudieron calcular los hashes.", { tipo: "error" });
    } finally {
      setCalculando(false);
    }
  };

  const cotejar = async (e) => {
    e.preventDefault();
    setCotejando(true);
    setResultado(null);
    try {
      const { data } = await api.post(`/archivos/${archivo.id}/cotejar`, {
        herramienta: herramienta === "otra" ? otraHerramienta : herramienta,
        referencia: referencia || null,
        texto,
      });
      setResultado(data);
      notificar(data.mensaje, { tipo: data.resultado === "no_coincide" ? "error" : "success" });
      onCambio?.();
      onHistorial?.();
    } catch (err) {
      const d = err.response?.data?.detail;
      notificar(typeof d === "string" ? d : "Revisa los datos del cotejo (pega al menos un hash completo).", {
        tipo: "error",
      });
    } finally {
      setCotejando(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-1 gap-space-sm flex-wrap">
        <span className="font-label-ui text-label-ui text-outline uppercase tracking-wider">
          Hashes de la evidencia (original)
        </span>
        <div className="flex items-center gap-space-md">
          {puedeCotejar && faltanAdicionales && (
            <button
              onClick={calcular}
              disabled={calculando}
              className="inline-flex items-center gap-1 font-label-ui text-label-ui text-primary hover:underline disabled:opacity-60"
            >
              <span className="material-symbols-outlined text-base">calculate</span>
              {calculando ? "Calculando..." : "Calcular SHA-1 y MD5"}
            </button>
          )}
          {puedeCotejar && (
            <button
              onClick={() => setAbierto(!abierto)}
              className="inline-flex items-center gap-1 font-label-ui text-label-ui text-primary hover:underline"
            >
              <span className="material-symbols-outlined text-base">compare_arrows</span>
              {abierto ? "Cerrar cotejo" : "Cotejar con Cellebrite / FTK"}
            </button>
          )}
        </div>
      </div>

      <dl className="flex flex-col gap-1">
        <FilaHash etiqueta="SHA-256" valor={archivo.hash_original} />
        <FilaHash etiqueta="SHA-1" valor={archivo.hash_sha1} />
        <FilaHash etiqueta="MD5" valor={archivo.hash_md5} />
      </dl>
      {faltanAdicionales && (
        <p className="font-body-sm text-body-sm text-outline mt-1">
          Este archivo se subió antes del doble hash: SHA-1 y MD5 se calculan leyendo el original, solo si su SHA-256
          sigue intacto.
        </p>
      )}

      {abierto && (
        <form
          onSubmit={cotejar}
          className="mt-space-sm bg-surface-container-high rounded-lg p-space-sm flex flex-col gap-space-sm"
        >
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            Pega el hash del informe de la herramienta con la que hiciste la extracción. Puede ser un hash suelto o el
            bloque completo (p. ej. <span className="font-label-code-sm text-label-code-sm">MD5 checksum: …</span>,{" "}
            <span className="font-label-code-sm text-label-code-sm">SHA1 checksum: …</span>): se reconocen MD5, SHA-1 y
            SHA-256.
          </p>
          <div className="grid sm:grid-cols-2 gap-space-sm">
            <label className="flex flex-col gap-1">
              <span className="font-label-ui text-label-ui text-on-surface-variant">Herramienta</span>
              <select value={herramienta} onChange={(e) => setHerramienta(e.target.value)} className={claseCampo}>
                {HERRAMIENTAS.map((h) => (
                  <option key={h} value={h}>{h}</option>
                ))}
                <option value="otra">Otra…</option>
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="font-label-ui text-label-ui text-on-surface-variant">N° de informe o extracción (opcional)</span>
              <input maxLength={200} value={referencia} onChange={(e) => setReferencia(e.target.value)} className={claseCampo} />
            </label>
            {herramienta === "otra" && (
              <label className="flex flex-col gap-1 sm:col-span-2">
                <span className="font-label-ui text-label-ui text-on-surface-variant">Nombre de la herramienta</span>
                <input required maxLength={80} value={otraHerramienta} onChange={(e) => setOtraHerramienta(e.target.value)} className={claseCampo} />
              </label>
            )}
          </div>
          <label className="flex flex-col gap-1">
            <span className="font-label-ui text-label-ui text-on-surface-variant">Hash o texto del informe</span>
            <textarea
              required
              rows={4}
              minLength={32}
              maxLength={20000}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              placeholder={"MD5 checksum:    9e107d9d372bb6826bd81d3542a419d6\nSHA1 checksum:   2fd4e1c67a2d28fced849ee1bb76e7391b93eb12"}
              className={`${claseCampo} font-label-code-sm text-label-code-sm`}
            />
          </label>
          <p className="font-body-sm text-body-sm text-outline">
            Ojo con imágenes E01: FTK Imager reporta el hash de los <em>datos adquiridos</em>, no el del archivo .E01.
            Para cotejar, sube la imagen en formato RAW (.dd) o usa el hash del contenedor si la herramienta lo indica.
          </p>
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={cotejando || texto.trim().length < 32}
              className="px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui disabled:opacity-60"
            >
              {cotejando ? "Cotejando..." : "Cotejar"}
            </button>
          </div>

          {resultado && (
            <div className={`rounded-lg border p-space-sm flex flex-col gap-2 ${RESULTADO[resultado.resultado]?.clase}`}>
              <div className="flex items-center gap-2 flex-wrap">
                <InsigniaResultado resultado={resultado.resultado} />
                <span className="font-body-sm text-body-sm text-on-surface">{resultado.mensaje}</span>
              </div>
              <ul className="flex flex-col gap-1">
                {resultado.hashes.map((h) => (
                  <li key={h.valor} className="grid grid-cols-[1.25rem_4.5rem_1fr] gap-2 items-start">
                    <span className={`material-symbols-outlined text-base ${h.coincide ? "text-tertiary" : "text-error"}`}>
                      {h.coincide ? "check_circle" : "cancel"}
                    </span>
                    <span className="font-label-ui text-label-ui text-on-surface-variant pt-0.5">{ETIQUETA[h.algoritmo]}</span>
                    <span className="font-label-code-sm text-label-code-sm text-on-surface break-all">{h.valor}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </form>
      )}

      {cotejos.length > 0 && (
        <div className="mt-space-sm">
          <span className="font-label-ui text-label-ui text-outline block mb-1">Cotejos registrados</span>
          <ul className="flex flex-col gap-1.5">
            {cotejos.map((c) => (
              <li key={c.fecha} className="flex items-center gap-2 flex-wrap font-body-sm text-body-sm">
                <InsigniaResultado resultado={c.resultado} />
                <span className="text-on-surface">{c.herramienta}</span>
                {c.referencia && <span className="text-on-surface-variant">· {c.referencia}</span>}
                <span className="text-on-surface-variant">
                  · {c.hashes.map((h) => ETIQUETA[h.algoritmo]).filter((x, i, t) => t.indexOf(x) === i).join(", ")}
                </span>
                <span className="text-outline">· {c.usuario}</span>
                <span className="text-outline font-label-code-sm text-label-code-sm">
                  · {new Date(c.fecha).toLocaleString("es-PE", { dateStyle: "medium", timeStyle: "short" })}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
