import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { useToast } from "./Toast";
import { puede } from "../permisos";

// Sprint 5 (épica H19): procedimiento pericial dentro del caso.
// El backend devuelve en `acciones` lo que el usuario puede hacer en cada pericia;
// aquí solo se muestran esos botones.

const PASOS = [
  { estado: "designada", texto: "Designada" },
  { estado: "emitida", texto: "Emitida" },
  { estado: "en_traslado", texto: "Traslado" },
  { estado: "observada", texto: "Observada" },
  { estado: "en_absolucion", texto: "Absolución" },
  { estado: "concluida", texto: "Concluida" },
];
const ORDEN = { designada: 0, emitida: 1, en_traslado: 2, observada: 3, en_absolucion: 4, absuelta: 4, concluida: 5 };

const EVENTO = {
  designacion: { icono: "gavel", texto: "Designación" },
  designacion_parte: { icono: "person_add", texto: "Perito de parte" },
  consulta: { icono: "visibility", texto: "Consulta del perito de parte" },
  emision: { icono: "description", texto: "Pericia emitida" },
  traslado: { icono: "forward_to_inbox", texto: "Traslado" },
  observacion: { icono: "rate_review", texto: "Observación" },
  conocimiento: { icono: "campaign", texto: "Puesta en conocimiento" },
  absolucion: { icono: "task", texto: "Absolución" },
  absuelta: { icono: "done_all", texto: "Absuelta" },
  conclusion: { icono: "verified", texto: "Concluida" },
  subrogacion: { icono: "swap_horiz", texto: "Subrogación" },
  descarga_informe: { icono: "download", texto: "Descarga del informe" },
  aceptacion: { icono: "how_to_reg", texto: "Acepta el cargo" },
  inhibicion: { icono: "person_off", texto: "Inhibición" },
  juramento: { icono: "front_hand", texto: "Juramento" },
  consulta_acta: { icono: "visibility", texto: "Consulta del acta de juramento" },
};

const input =
  "px-2.5 py-2 rounded-md bg-surface-container-lowest text-on-surface font-body-sm text-body-sm placeholder:text-outline/50 focus:outline-none focus:ring-1 focus:ring-primary/50";
const btnPrim = "px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui disabled:opacity-60";
const btnSec =
  "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface font-label-ui text-label-ui hover:bg-surface-container";
const btnTxt = "px-3 py-1.5 rounded-lg font-label-ui text-label-ui text-on-surface-variant hover:bg-surface-container";

function fecha(iso, conHora = true) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-PE", conHora ? { dateStyle: "medium", timeStyle: "short" } : { dateStyle: "medium" });
}

function detalleError(err, porDefecto) {
  const d = err.response?.data?.detail;
  return typeof d === "string" ? d : porDefecto;
}

async function bajar(url, nombre) {
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

function usePadron(tipo) {
  const [lista, setLista] = useState([]);
  useEffect(() => {
    let activo = true;
    api
      .get("/peritos", { params: { tipo, solo_habilitados: true } })
      .then(({ data }) => activo && setLista(data))
      .catch(() => {});
    return () => {
      activo = false;
    };
  }, [tipo]);
  return lista;
}

function Persona({ p }) {
  if (!p) return <span className="text-outline">—</span>;
  return (
    <span>
      <span className="text-on-surface">{p.nombre}</span>
      {(p.institucion || p.registro_profesional) && (
        <span className="text-outline"> · {[p.institucion, p.registro_profesional].filter(Boolean).join(" · ")}</span>
      )}
    </span>
  );
}

function Pasos({ estado }) {
  const actual = ORDEN[estado] ?? 0;
  return (
    <ol className="flex items-center gap-1 flex-wrap">
      {PASOS.map((p, i) => (
        <li key={p.estado} className="flex items-center gap-1">
          <span
            className={`px-2 py-0.5 rounded-full font-label-ui text-label-ui ${
              i < actual
                ? "bg-tertiary/15 text-tertiary"
                : i === actual
                ? "bg-primary/20 text-primary ring-1 ring-primary/40"
                : "bg-surface-container-high text-outline"
            }`}
          >
            {p.texto}
          </span>
          {i < PASOS.length - 1 && <span className="text-outline/50">›</span>}
        </li>
      ))}
    </ol>
  );
}

/* ----------------------------------------------------------- formularios */
const ESPECIALIDADES = { audio: "Audio", video: "Video", informatica: "Informática", telefonia: "Telefonía" };

function FormDesignar({ caso, onListo, onCancelar }) {
  const casoId = caso.id;
  const especialidadesCaso = caso.especialidades?.length ? caso.especialidades : [caso.especialidad];
  const [especialidad, setEspecialidad] = useState(especialidadesCaso[0]);
  // Sprint 5: solo peritos oficiales de la especialidad elegida
  const peritos = usePadron("perito").filter((p) => p.especialidad === especialidad);
  const [perito, setPerito] = useState("");
  const [disposicion, setDisposicion] = useState("");
  const [objetivos, setObjetivos] = useState([""]);
  const [plazo, setPlazo] = useState(15);
  const [plazoAceptar, setPlazoAceptar] = useState(3);
  const [enviando, setEnviando] = useState(false);
  const { notificar } = useToast();

  const enviar = async (e) => {
    e.preventDefault();
    setEnviando(true);
    try {
      const { data } = await api.post(`/casos/${casoId}/pericias`, {
        perito_oficial_id: perito,
        especialidad,
        disposicion_fiscal: disposicion,
        objetivos: objetivos.filter((o) => o.trim()),
        plazo_dias: Number(plazo),
        plazo_aceptacion_dias: Number(plazoAceptar),
      });
      notificar(`Pericia ${data.codigo} designada. El perito tiene ${plazoAceptar} día(s) para aceptar o inhibirse.`, { tipo: "success" });
      onListo();
    } catch (err) {
      notificar(detalleError(err, "Revisa los datos de la designación."), { tipo: "error" });
    } finally {
      setEnviando(false);
    }
  };

  return (
    <form onSubmit={enviar} className="bg-surface-container-high rounded-lg p-space-md flex flex-col gap-space-sm mb-space-md">
      <h3 className="font-headline-sm text-headline-sm text-on-surface">Designar perito oficial</h3>
      <div className="grid sm:grid-cols-5 gap-space-sm">
        <label className="flex flex-col gap-1">
          <span className="font-label-code-sm text-label-code-sm text-outline">Especialidad de la pericia</span>
          <select value={especialidad} onChange={(e) => { setEspecialidad(e.target.value); setPerito(""); }} className={input}>
            {especialidadesCaso.map((k) => <option key={k} value={k}>{ESPECIALIDADES[k]}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 sm:col-span-1">
          <span className="font-label-code-sm text-label-code-sm text-outline">Perito oficial (padrón)</span>
          <select required value={perito} onChange={(e) => setPerito(e.target.value)} className={input}>
            <option value="">{peritos.length ? "Elegir…" : "No hay peritos de esta especialidad"}</option>
            {peritos.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nombre} · {p.institucion || "sin institución"} ({p.pericias_activas} activas)
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="font-label-code-sm text-label-code-sm text-outline">Disposición fiscal</span>
          <input required value={disposicion} onChange={(e) => setDisposicion(e.target.value)} placeholder="Disposición Fiscal N° 045-2026-MP" className={input} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="font-label-code-sm text-label-code-sm text-outline">Plazo de la pericia (días)</span>
          <input required type="number" min={1} max={365} value={plazo} onChange={(e) => setPlazo(e.target.value)} className={input} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="font-label-code-sm text-label-code-sm text-outline">Días para aceptar el cargo</span>
          <input required type="number" min={1} max={15} value={plazoAceptar} onChange={(e) => setPlazoAceptar(e.target.value)} className={input} />
        </label>
      </div>
      <div className="flex flex-col gap-1.5">
        <span className="font-label-code-sm text-label-code-sm text-outline">Objetivos de la pericia</span>
        {objetivos.map((o, i) => (
          <div key={i} className="flex gap-2">
            <span className="font-label-code-sm text-label-code-sm text-outline pt-2.5 w-5">{i + 1}.</span>
            <input
              required={i === 0}
              value={o}
              onChange={(e) => setObjetivos(objetivos.map((x, j) => (j === i ? e.target.value : x)))}
              placeholder={i === 0 ? "Ej. Extraer los mensajes de WhatsApp del 01/10 al 15/10" : "Otro objetivo (opcional)"}
              className={`${input} flex-1`}
            />
            {objetivos.length > 1 && (
              <button type="button" onClick={() => setObjetivos(objetivos.filter((_, j) => j !== i))} className="text-outline hover:text-error px-1">
                <span className="material-symbols-outlined text-base">close</span>
              </button>
            )}
          </div>
        ))}
        <button type="button" onClick={() => setObjetivos([...objetivos, ""])} className="self-start font-label-ui text-label-ui text-primary hover:underline ml-7">
          + Agregar objetivo
        </button>
      </div>
      <div className="flex justify-end gap-space-sm">
        <button type="button" onClick={onCancelar} className={btnTxt}>Cancelar</button>
        <button type="submit" disabled={enviando} className={btnPrim}>{enviando ? "Designando..." : "Designar"}</button>
      </div>
    </form>
  );
}

function FormEmitir({ pericia, onListo, onCancelar }) {
  const [archivo, setArchivo] = useState(null);
  const [conclusiones, setConclusiones] = useState(pericia.objetivos.map(() => ""));
  const [enviando, setEnviando] = useState(false);
  const { notificar } = useToast();

  const enviar = async (e) => {
    e.preventDefault();
    setEnviando(true);
    const datos = new FormData();
    datos.append("informe", archivo);
    datos.append("conclusiones", JSON.stringify(conclusiones));
    try {
      await api.post(`/pericias/${pericia.id}/emitir`, datos);
      notificar("Pericia emitida. Se notificó al fiscal.", { tipo: "success" });
      onListo();
    } catch (err) {
      notificar(detalleError(err, "No se pudo emitir la pericia."), { tipo: "error" });
    } finally {
      setEnviando(false);
    }
  };

  return (
    <form onSubmit={enviar} className="bg-surface-container-high rounded-lg p-space-sm flex flex-col gap-space-sm">
      <span className="font-label-ui text-label-ui text-outline uppercase tracking-wider">Emitir pericia oficial</span>
      <input type="file" required accept=".pdf,.doc,.docx" onChange={(e) => setArchivo(e.target.files[0])} className="font-body-sm text-body-sm text-on-surface-variant" />
      {pericia.objetivos.map((o, i) => (
        <label key={i} className="flex flex-col gap-1">
          <span className="font-body-sm text-body-sm text-on-surface-variant">{i + 1}. {o.texto}</span>
          <textarea required rows={2} value={conclusiones[i]} placeholder="Conclusión para este objetivo"
            onChange={(e) => setConclusiones(conclusiones.map((x, j) => (j === i ? e.target.value : x)))} className={input} />
        </label>
      ))}
      <div className="flex justify-end gap-space-sm">
        <button type="button" onClick={onCancelar} className={btnTxt}>Cancelar</button>
        <button type="submit" disabled={enviando || !archivo} className={btnPrim}>{enviando ? "Emitiendo..." : "Emitir pericia"}</button>
      </div>
    </form>
  );
}

function FormSimple({ titulo, children, onEnviar, onCancelar, textoBoton }) {
  const [enviando, setEnviando] = useState(false);
  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        setEnviando(true);
        try {
          await onEnviar();
        } finally {
          setEnviando(false);
        }
      }}
      className="bg-surface-container-high rounded-lg p-space-sm flex flex-col gap-space-sm"
    >
      <span className="font-label-ui text-label-ui text-outline uppercase tracking-wider">{titulo}</span>
      {children}
      <div className="flex justify-end gap-space-sm">
        <button type="button" onClick={onCancelar} className={btnTxt}>Cancelar</button>
        <button type="submit" disabled={enviando} className={btnPrim}>{enviando ? "Enviando..." : textoBoton}</button>
      </div>
    </form>
  );
}

function FormSubrogar({ pericia, onListo, onCancelar }) {
  const [tipo, setTipo] = useState("oficial");
  const oficiales = usePadron("perito");
  const partes = usePadron("perito_parte");
  const [motivos, setMotivos] = useState([]);
  const actuales = pericia.designaciones.filter((d) => d.activa && d.tipo === tipo);
  const [saliente, setSaliente] = useState("");
  const [entrante, setEntrante] = useState("");
  const [motivo, setMotivo] = useState("impedimento");
  const [documento, setDocumento] = useState("");
  const [detalle, setDetalle] = useState("");
  const { notificar } = useToast();
  const candidatos = (tipo === "oficial" ? oficiales.filter((p) => !pericia.especialidad || p.especialidad === pericia.especialidad) : partes).filter(
    (p) => !actuales.some((d) => d.perito.id === p.id)
  );

  useEffect(() => {
    api.get("/pericias-motivos-subrogacion").then(({ data }) => setMotivos(data)).catch(() => {});
  }, []);

  return (
    <FormSimple
      titulo="Subrogar perito (CPP art. 175)"
      textoBoton="Subrogar"
      onCancelar={onCancelar}
      onEnviar={async () => {
        try {
          await api.post(`/pericias/${pericia.id}/subrogar`, {
            tipo,
            saliente_id: saliente || actuales[0]?.perito.id,
            entrante_id: entrante,
            motivo,
            documento,
            detalle,
          });
          notificar("Perito subrogado. El saliente perdió el acceso; queda en el historial.", { tipo: "success" });
          onListo();
        } catch (err) {
          notificar(detalleError(err, "No se pudo subrogar."), { tipo: "error" });
        }
      }}
    >
      <div className="grid sm:grid-cols-2 gap-space-sm">
        <select value={tipo} onChange={(e) => { setTipo(e.target.value); setSaliente(""); setEntrante(""); }} className={input}>
          <option value="oficial">Perito oficial</option>
          <option value="parte">Perito de parte</option>
        </select>
        <select required value={saliente} onChange={(e) => setSaliente(e.target.value)} className={input}>
          <option value="">Saliente…</option>
          {actuales.map((d) => <option key={d.id} value={d.perito.id}>{d.perito.nombre}</option>)}
        </select>
        <select required value={entrante} onChange={(e) => setEntrante(e.target.value)} className={input}>
          <option value="">Entrante (padrón)…</option>
          {candidatos.map((p) => <option key={p.id} value={p.id}>{p.nombre} · {p.institucion || "—"}</option>)}
        </select>
        <select value={motivo} onChange={(e) => setMotivo(e.target.value)} className={input}>
          {motivos.map((m) => <option key={m.valor} value={m.valor}>{m.etiqueta}</option>)}
        </select>
        <input required value={documento} onChange={(e) => setDocumento(e.target.value)} placeholder="Disposición que ordena la subrogación" className={input} />
        <input value={detalle} onChange={(e) => setDetalle(e.target.value)} placeholder="Detalle (opcional)" className={input} />
      </div>
    </FormSimple>
  );
}

/* ----------------------------------------------------------- aceptación del cargo y juramento (CPP art. 174) */
function FormInhibirse({ pericia, onListo, onCancelar }) {
  const [motivos, setMotivos] = useState([]);
  const [motivo, setMotivo] = useState("amistad_enemistad");
  const [detalle, setDetalle] = useState("");
  const { notificar } = useToast();
  useEffect(() => {
    api.get("/pericias-motivos-inhibicion").then(({ data }) => setMotivos(data)).catch(() => {});
  }, []);
  return (
    <FormSimple
      titulo="Inhibirme del cargo"
      textoBoton="Inhibirme"
      onCancelar={onCancelar}
      onEnviar={async () => {
        if (!window.confirm("Al inhibirte dejas el cargo y pierdes el acceso a este caso. ¿Continuar?")) return;
        try {
          await api.post(`/pericias/${pericia.id}/inhibirse`, { motivo, detalle });
          notificar("Te inhibiste del cargo. Se notificó al fiscal.", { tipo: "success" });
          onListo();
        } catch (err) {
          notificar(detalleError(err, "Explica el motivo (al menos 10 caracteres)."), { tipo: "error" });
        }
      }}
    >
      <select value={motivo} onChange={(e) => setMotivo(e.target.value)} className={input}>
        {motivos.map((m) => <option key={m.valor} value={m.valor}>{m.etiqueta}</option>)}
      </select>
      <textarea required minLength={10} rows={3} value={detalle} onChange={(e) => setDetalle(e.target.value)}
        placeholder="Ej. Conozco personalmente al investigado: fuimos compañeros de trabajo entre 2019 y 2022." className={input} />
    </FormSimple>
  );
}

function FormJuramento({ pericia, usuario, onListo, onCancelar }) {
  const [forma, setForma] = useState("juramento");
  const [firma, setFirma] = useState("");
  const [sinImpedimento, setSinImpedimento] = useState(false);
  const { notificar } = useToast();
  return (
    <FormSimple
      titulo="Prestar juramento (CPP art. 174)"
      textoBoton={forma === "juramento" ? "Juro" : "Prometo por mi honor"}
      onCancelar={onCancelar}
      onEnviar={async () => {
        try {
          await api.post(`/pericias/${pericia.id}/juramentar`, { forma, firma, sin_impedimento: sinImpedimento });
          notificar("Juramento registrado. El fiscal ya puede ver el acta.", { tipo: "success" });
          onListo();
        } catch (err) {
          notificar(detalleError(err, "No se pudo registrar el juramento."), { tipo: "error" });
        }
      }}
    >
      <div className="flex gap-space-md font-body-sm text-body-sm text-on-surface">
        <label className="flex items-center gap-1.5">
          <input type="radio" checked={forma === "juramento"} onChange={() => setForma("juramento")} /> Juramento
        </label>
        <label className="flex items-center gap-1.5">
          <input type="radio" checked={forma === "promesa"} onChange={() => setForma("promesa")} /> Promesa de honor
        </label>
      </div>
      <p className="font-body-sm text-body-sm text-on-surface-variant bg-surface-container-lowest rounded-md p-space-sm">
        Yo, <b className="text-on-surface">{usuario?.nombre}</b>, {forma === "juramento" ? "JURO" : "PROMETO POR MI HONOR"} desempeñar con
        verdad y diligencia el cargo de perito oficial en la pericia {pericia.codigo} del caso {pericia.caso_numero}, y declaro que no
        me encuentro incurso en ninguna causal de impedimento y que guardaré reserva sobre la información a la que acceda.
      </p>
      <label className="flex items-start gap-2 font-body-sm text-body-sm text-on-surface">
        <input type="checkbox" required checked={sinImpedimento} onChange={(e) => setSinImpedimento(e.target.checked)} className="mt-1" />
        Declaro que no conozco ni tengo relación con las partes, ni otro impedimento para ejercer el cargo.
      </label>
      <input required value={firma} onChange={(e) => setFirma(e.target.value)} className={input}
        placeholder={`Firma: escribe tu nombre completo (${usuario?.nombre || ""})`} />
    </FormSimple>
  );
}

function FormReemplazo({ pericia, onListo, onCancelar }) {
  const inhibidos = pericia.designaciones.filter((d) => d.aceptacion === "inhibida").map((d) => d.perito.id);
  const candidatos = usePadron("perito").filter(
    (p) => (!pericia.especialidad || p.especialidad === pericia.especialidad) && !inhibidos.includes(p.id)
  );
  const [entrante, setEntrante] = useState("");
  const [documento, setDocumento] = useState("");
  const [plazo, setPlazo] = useState(3);
  const { notificar } = useToast();
  return (
    <FormSimple
      titulo="Designar nuevo perito oficial"
      textoBoton="Designar"
      onCancelar={onCancelar}
      onEnviar={async () => {
        try {
          await api.post(`/pericias/${pericia.id}/reemplazar-oficial`, { entrante_id: entrante, documento, plazo_aceptacion_dias: Number(plazo) });
          notificar("Nuevo perito designado. Se le notificó para que acepte o se inhiba.", { tipo: "success" });
          onListo();
        } catch (err) {
          notificar(detalleError(err, "No se pudo designar."), { tipo: "error" });
        }
      }}
    >
      <div className="grid sm:grid-cols-3 gap-space-sm">
        <select required value={entrante} onChange={(e) => setEntrante(e.target.value)} className={input}>
          <option value="">{candidatos.length ? "Perito oficial (padrón)…" : "No hay otros peritos de esta especialidad"}</option>
          {candidatos.map((p) => <option key={p.id} value={p.id}>{p.nombre} · {p.institucion || "—"}</option>)}
        </select>
        <input required value={documento} onChange={(e) => setDocumento(e.target.value)} placeholder="Disposición de la nueva designación" className={input} />
        <label className="flex items-center gap-2 font-body-sm text-body-sm text-on-surface-variant">
          Días para aceptar
          <input type="number" min={1} max={15} value={plazo} onChange={(e) => setPlazo(e.target.value)} className={`${input} w-20`} />
        </label>
      </div>
    </FormSimple>
  );
}

/** Estado del cargo del perito oficial: lo que el fiscal necesita ver de un vistazo. */
function EstadoCargo({ pericia, onCambio }) {
  const [verTexto, setVerTexto] = useState(false);
  const { notificar } = useToast();
  const d = pericia.designaciones.find((x) => x.activa && x.tipo === "oficial");
  const ultimaInhibicion = [...pericia.designaciones].reverse().find((x) => x.aceptacion === "inhibida");
  const caja = "rounded-lg px-space-sm py-2 font-body-sm text-body-sm flex flex-col gap-1";

  if (!d) {
    return (
      <div className={`${caja} bg-error/10 text-error`}>
        <div className="flex items-center gap-2"><span className="material-symbols-outlined text-base">person_off</span>
          Sin perito oficial: {ultimaInhibicion ? `${ultimaInhibicion.perito.nombre} se inhibió.` : "falta designar."}</div>
        {ultimaInhibicion && (
          <div className="text-on-surface-variant">
            {ultimaInhibicion.inhibicion_motivo} — “{ultimaInhibicion.inhibicion_detalle}” · {fecha(ultimaInhibicion.subrogado_en)}
          </div>
        )}
      </div>
    );
  }
  if (d.aceptacion === "pendiente") {
    return (
      <div className={`${caja} ${d.aceptacion_vencida ? "bg-error/10 text-error" : "bg-amber-400/10 text-amber-400"}`}>
        <div className="flex items-center gap-2"><span className="material-symbols-outlined text-base">hourglass_top</span>
          {d.perito.nombre}: pendiente de aceptar el cargo · {d.aceptacion_vencida ? "plazo vencido el" : "vence"} {fecha(d.aceptacion_vence_en)}</div>
        {d.aceptacion_vencida && <div className="text-on-surface-variant">No respondió a tiempo: puedes subrogarlo con el motivo “No aceptó el cargo en el plazo”.</div>}
      </div>
    );
  }
  if (!d.juramento_en) {
    return (
      <div className={`${caja} bg-amber-400/10 text-amber-400`}>
        <div className="flex items-center gap-2"><span className="material-symbols-outlined text-base">how_to_reg</span>
          {d.perito.nombre} aceptó el cargo el {fecha(d.aceptada_en)} · falta que preste juramento</div>
      </div>
    );
  }
  if (d.juramento_forma === "historico") {
    return (
      <div className={`${caja} bg-surface-container-high text-on-surface-variant`}>
        <div className="flex items-center gap-2"><span className="material-symbols-outlined text-base">history</span>
          Designación anterior a la juramentación en línea (sin acta).</div>
      </div>
    );
  }
  return (
    <div className={`${caja} bg-tertiary/10 text-tertiary`}>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="material-symbols-outlined text-base">verified_user</span>
        {d.perito.nombre} {d.juramento_forma === "juramento" ? "juró" : "prometió por su honor"} el {fecha(d.juramento_en)}
        <button onClick={() => setVerTexto(!verTexto)} className="text-primary hover:underline ml-1">{verTexto ? "ocultar texto" : "ver texto"}</button>
        <button
          onClick={() =>
            bajar(`/designaciones-pericia/${d.id}/acta`, `Acta_juramento_${pericia.codigo}.pdf`)
              .then(onCambio)
              .catch(() => notificar("No se pudo descargar el acta.", { tipo: "error" }))
          }
          className="inline-flex items-center gap-1 text-primary hover:underline"
        >
          <span className="material-symbols-outlined text-base">picture_as_pdf</span>Acta de juramento
        </button>
      </div>
      {verTexto && (
        <div className="text-on-surface-variant">
          <p>“{d.juramento_texto}”</p>
          <p className="font-label-code-sm text-label-code-sm text-outline mt-1">Aceptó el {fecha(d.aceptada_en)} · SHA-256 {d.juramento_hash?.slice(0, 24)}…</p>
        </div>
      )}
    </div>
  );
}

/* ----------------------------------------------------------- tarjeta de pericia */
function TarjetaPericia({ pericia, usuario, onCambio }) {
  const [form, setForm] = useState(null);
  const [verHistorial, setVerHistorial] = useState(false);
  const [plazoTraslado, setPlazoTraslado] = useState(5);
  const [obsTexto, setObsTexto] = useState("");
  const [obsAnexo, setObsAnexo] = useState(null);
  const [respuestas, setRespuestas] = useState({});
  const [peritoParte, setPeritoParte] = useState("");
  const [docParte, setDocParte] = useState("");
  const partes = usePadron("perito_parte");
  const { notificar } = useToast();
  const a = pericia.acciones;

  const listo = (mensaje) => {
    if (mensaje) notificar(mensaje, { tipo: "success" });
    setForm(null);
    onCambio();
  };

  const accion = async (url, cuerpo, mensaje) => {
    try {
      await api.post(url, cuerpo);
      listo(mensaje);
    } catch (err) {
      notificar(detalleError(err, "No se pudo completar la acción."), { tipo: "error" });
    }
  };

  const pendientes = pericia.observaciones.filter((o) => !o.respuesta).length;

  return (
    <div className="border border-outline-variant/30 rounded-xl p-space-md flex flex-col gap-space-sm">
      <div className="flex items-start justify-between gap-space-md flex-wrap">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-label-code-lg text-label-code-lg text-on-surface">{pericia.codigo}</span>
            {pericia.especialidad && (
              <span className="px-2 py-0.5 rounded bg-surface-container-high text-secondary font-label-ui text-label-ui uppercase tracking-wider">
                {ESPECIALIDADES[pericia.especialidad] || pericia.especialidad}
              </span>
            )}
            <span className="font-body-sm text-body-sm text-on-surface-variant">· {pericia.disposicion_fiscal}</span>
          </div>
          <div className="mt-1.5"><Pasos estado={pericia.estado} /></div>
        </div>
        <div className="text-right font-label-code-sm text-label-code-sm text-outline">
          <div>Designada {fecha(pericia.designada_en)} por {pericia.designada_por}</div>
          {pericia.estado === "designada" && (
            <div className={new Date(pericia.fecha_limite) < new Date() ? "text-error" : ""}>Plazo: vence {fecha(pericia.fecha_limite, false)}</div>
          )}
          {pericia.traslado_vence_en && ["en_traslado", "observada"].includes(pericia.estado) && (
            <div className={pericia.traslado_vencido ? "text-error" : "text-amber-400"}>
              Traslado {pericia.traslado_vencido ? "vencido" : "vence"} {fecha(pericia.traslado_vence_en)}
            </div>
          )}
        </div>
      </div>

      <div className="grid sm:grid-cols-2 gap-x-space-md gap-y-1 font-body-sm text-body-sm">
        <div><span className="text-outline">Perito oficial: </span><Persona p={pericia.perito_oficial} /></div>
        <div>
          <span className="text-outline">Perito(s) de parte: </span>
          {pericia.peritos_parte.length ? pericia.peritos_parte.map((p, i) => <span key={p.id}>{i > 0 && ", "}<Persona p={p} /></span>) : <span className="text-outline">ninguno acreditado</span>}
        </div>
      </div>

      {/* Estado del cargo del perito oficial (aceptación, inhibición, juramento y acta) */}
      {(pericia.estado !== "concluida" || pericia.designaciones.some((d) => d.activa && d.tipo === "oficial" && d.tiene_acta)) && (
        <EstadoCargo pericia={pericia} onCambio={onCambio} />
      )}

      <div>
        <span className="font-label-ui text-label-ui text-outline uppercase tracking-wider">Objetivos de la pericia</span>
        <ol className="mt-1 flex flex-col gap-1.5">
          {pericia.objetivos.map((o, i) => (
            <li key={i} className="font-body-sm text-body-sm">
              <span className="text-on-surface">{i + 1}. {o.texto}</span>
              {o.conclusion && <div className="ml-4 text-on-surface-variant"><span className="text-tertiary">Conclusión:</span> {o.conclusion}</div>}
            </li>
          ))}
        </ol>
      </div>

      {pericia.informe_nombre && (
        <div className="flex items-center gap-space-sm flex-wrap font-body-sm text-body-sm">
          <button onClick={() => bajar(`/pericias/${pericia.id}/informe`, `${pericia.codigo}_${pericia.informe_nombre}`).then(onCambio)} className={btnSec}>
            <span className="material-symbols-outlined text-base">picture_as_pdf</span>
            Informe pericial
          </button>
          <span className="font-label-code-sm text-label-code-sm text-outline">
            emitido {fecha(pericia.emitida_en)} · SHA-256 {pericia.informe_hash.slice(0, 16)}…
          </span>
        </div>
      )}

      {pericia.observaciones.length > 0 && (
        <div>
          <span className="font-label-ui text-label-ui text-outline uppercase tracking-wider">
            Observaciones de la parte ({pericia.observaciones.length}{pendientes ? `, ${pendientes} por absolver` : ""})
          </span>
          <ul className="mt-1 flex flex-col gap-space-sm">
            {pericia.observaciones.map((o) => (
              <li key={o.id} className="bg-surface-container-high rounded-lg p-space-sm font-body-sm text-body-sm">
                <p className="text-on-surface">{o.texto}</p>
                <p className="mt-1 font-label-code-sm text-label-code-sm text-outline">
                  {o.autor.nombre} · {fecha(o.creada_en)}
                  {o.anexo_nombre && (
                    <button onClick={() => bajar(`/observaciones-pericia/${o.id}/anexo`, o.anexo_nombre)} className="ml-2 text-primary hover:underline">
                      anexo: {o.anexo_nombre}
                    </button>
                  )}
                </p>
                {o.respuesta ? (
                  <div className="mt-2 border-l-2 border-tertiary pl-2.5">
                    <p className="text-on-surface-variant"><span className="text-tertiary">Absolución:</span> {o.respuesta}</p>
                    <p className="font-label-code-sm text-label-code-sm text-outline">{o.respondida_por} · {fecha(o.respondida_en)}</p>
                  </div>
                ) : (
                  a.includes("absolver") && (
                    <div className="mt-2 flex gap-2">
                      <input value={respuestas[o.id] || ""} onChange={(e) => setRespuestas({ ...respuestas, [o.id]: e.target.value })}
                        placeholder="Absolución del perito oficial" className={`${input} flex-1`} />
                      <button disabled={!respuestas[o.id]?.trim()} className={btnPrim}
                        onClick={() => accion(`/observaciones-pericia/${o.id}/absolver`, { respuesta: respuestas[o.id] }, "Observación absuelta.")}>
                        Absolver
                      </button>
                    </div>
                  )
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Acciones según el estado y el rol (las define el backend) */}
      {a.length > 0 && !form && (
        <div className="flex flex-wrap gap-space-sm">
          {a.includes("aceptar_cargo") && (
            <button
              onClick={() => window.confirm("¿Aceptas el cargo de perito oficial? Después deberás prestar juramento.") &&
                accion(`/pericias/${pericia.id}/aceptar`, {}, "Cargo aceptado. Ahora presta juramento.")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui"
            >
              <span className="material-symbols-outlined text-base">how_to_reg</span>Aceptar el cargo
            </button>
          )}
          {a.includes("inhibirse") && <button onClick={() => setForm("inhibirse")} className={btnSec}><span className="material-symbols-outlined text-base">person_off</span>Inhibirme (tengo un impedimento)</button>}
          {a.includes("juramentar") && (
            <button onClick={() => setForm("juramentar")} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui">
              <span className="material-symbols-outlined text-base">front_hand</span>Prestar juramento
            </button>
          )}
          {a.includes("reemplazar_oficial") && (
            <button onClick={() => setForm("reemplazo")} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui">
              <span className="material-symbols-outlined text-base">gavel</span>Designar nuevo perito oficial
            </button>
          )}
          {a.includes("emitir") && <button onClick={() => setForm("emitir")} className={btnSec}><span className="material-symbols-outlined text-base">upload_file</span>Emitir pericia</button>}
          {a.includes("correr_traslado") && <button onClick={() => setForm("traslado")} className={btnSec}><span className="material-symbols-outlined text-base">forward_to_inbox</span>Correr traslado</button>}
          {a.includes("observar") && <button onClick={() => setForm("observar")} className={btnSec}><span className="material-symbols-outlined text-base">rate_review</span>Formular observación</button>}
          {a.includes("poner_conocimiento") && (
            <button onClick={() => accion(`/pericias/${pericia.id}/conocimiento`, {}, "Se puso en conocimiento del perito oficial.")} className={btnSec}>
              <span className="material-symbols-outlined text-base">campaign</span>Poner en conocimiento del perito
            </button>
          )}
          {a.includes("concluir") && (
            <button onClick={() => window.confirm("¿Dar la pericia por concluida?") && accion(`/pericias/${pericia.id}/concluir`, {}, "Pericia concluida.")} className={btnSec}>
              <span className="material-symbols-outlined text-base">verified</span>Concluir pericia
            </button>
          )}
          {a.includes("designar_parte") && <button onClick={() => setForm("parte")} className={btnSec}><span className="material-symbols-outlined text-base">person_add</span>Acreditar perito de parte</button>}
          {a.includes("subrogar") && <button onClick={() => setForm("subrogar")} className={btnSec}><span className="material-symbols-outlined text-base">swap_horiz</span>Subrogar perito</button>}
        </div>
      )}

      {form === "inhibirse" && <FormInhibirse pericia={pericia} onListo={() => listo()} onCancelar={() => setForm(null)} />}
      {form === "juramentar" && <FormJuramento pericia={pericia} usuario={usuario} onListo={() => listo()} onCancelar={() => setForm(null)} />}
      {form === "reemplazo" && <FormReemplazo pericia={pericia} onListo={() => listo()} onCancelar={() => setForm(null)} />}
      {form === "emitir" && <FormEmitir pericia={pericia} onListo={() => listo()} onCancelar={() => setForm(null)} />}
      {form === "traslado" && (
        <FormSimple titulo="Correr traslado a la parte investigada" textoBoton="Correr traslado" onCancelar={() => setForm(null)}
          onEnviar={() => accion(`/pericias/${pericia.id}/traslado`, { plazo_dias: Number(plazoTraslado) }, "Traslado corrido. Se notificó al perito de parte.")}>
          <label className="flex items-center gap-2 font-body-sm text-body-sm text-on-surface-variant">
            Plazo para observar (días):
            <input type="number" min={1} max={60} value={plazoTraslado} onChange={(e) => setPlazoTraslado(e.target.value)} className={`${input} w-24`} />
          </label>
        </FormSimple>
      )}
      {form === "observar" && (
        <FormSimple titulo="Observación de la parte investigada" textoBoton="Registrar observación" onCancelar={() => setForm(null)}
          onEnviar={async () => {
            const datos = new FormData();
            datos.append("texto", obsTexto);
            if (obsAnexo) datos.append("anexo", obsAnexo);
            try {
              await api.post(`/pericias/${pericia.id}/observaciones`, datos);
              setObsTexto("");
              setObsAnexo(null);
              listo("Observación registrada. Se notificó al fiscal.");
            } catch (err) {
              notificar(detalleError(err, "No se pudo registrar la observación."), { tipo: "error" });
            }
          }}>
          <textarea required rows={3} value={obsTexto} onChange={(e) => setObsTexto(e.target.value)} placeholder="¿Qué observa la parte sobre la pericia o el procedimiento?" className={input} />
          <input type="file" onChange={(e) => setObsAnexo(e.target.files[0])} className="font-body-sm text-body-sm text-on-surface-variant" />
        </FormSimple>
      )}
      {form === "parte" && (
        <FormSimple titulo="Acreditar perito de parte" textoBoton="Acreditar" onCancelar={() => setForm(null)}
          onEnviar={() => accion(`/pericias/${pericia.id}/perito-parte`, { perito_id: peritoParte, documento: docParte }, "Perito de parte acreditado.")}>
          <div className="grid sm:grid-cols-2 gap-space-sm">
            <select required value={peritoParte} onChange={(e) => setPeritoParte(e.target.value)} className={input}>
              <option value="">Perito de parte (padrón)…</option>
              {partes.map((p) => <option key={p.id} value={p.id}>{p.nombre} · {p.institucion || "—"}</option>)}
            </select>
            <input value={docParte} onChange={(e) => setDocParte(e.target.value)} placeholder="Escrito de la defensa N°…" className={input} />
          </div>
        </FormSimple>
      )}
      {form === "subrogar" && <FormSubrogar pericia={pericia} onListo={() => listo()} onCancelar={() => setForm(null)} />}

      <button onClick={() => setVerHistorial(!verHistorial)} className="self-start font-label-ui text-label-ui text-primary hover:underline">
        {verHistorial ? "Ocultar" : "Ver"} historial de la pericia ({pericia.eventos.length})
      </button>
      {verHistorial && (
        <div className="grid md:grid-cols-2 gap-space-md">
          <ul className="flex flex-col gap-1.5">
            {pericia.eventos.map((e, i) => {
              const info = EVENTO[e.tipo] || { icono: "info", texto: e.tipo };
              return (
                <li key={i} className="flex items-start gap-2 font-body-sm text-body-sm">
                  <span className="material-symbols-outlined text-base text-primary">{info.icono}</span>
                  <div>
                    <span className="text-on-surface">{info.texto}</span>
                    <span className="text-outline"> · {e.usuario} · {fecha(e.fecha)}</span>
                    {e.detalle && <div className="text-on-surface-variant">{e.detalle}</div>}
                  </div>
                </li>
              );
            })}
          </ul>
          <div>
            <span className="font-label-ui text-label-ui text-outline uppercase tracking-wider">Peritos designados</span>
            <ul className="mt-1 flex flex-col gap-1.5">
              {pericia.designaciones.map((d) => (
                <li key={d.id} className="font-body-sm text-body-sm">
                  <span className={d.activa ? "text-on-surface" : "text-outline line-through"}>{d.perito.nombre}</span>
                  <span className="text-outline"> · {d.tipo === "oficial" ? "oficial" : "de parte"} · desde {fecha(d.designado_en, false)}</span>
                  {!d.activa && d.aceptacion === "inhibida" && (
                    <div className="text-error font-label-code-sm text-label-code-sm">
                      Se inhibió {fecha(d.subrogado_en)} · {d.inhibicion_motivo}
                    </div>
                  )}
                  {!d.activa && d.aceptacion !== "inhibida" && (
                    <div className="text-error font-label-code-sm text-label-code-sm">
                      Subrogado {fecha(d.subrogado_en)} · {d.motivo_subrogacion} · {d.documento_subrogacion}
                    </div>
                  )}
                  {d.tipo === "oficial" && d.juramento_en && d.juramento_forma !== "historico" && (
                    <div className="text-tertiary font-label-code-sm text-label-code-sm">
                      {d.juramento_forma === "juramento" ? "Juramentó" : "Promesa de honor"} {fecha(d.juramento_en)}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Pericias({ caso, usuario }) {
  const [pericias, setPericias] = useState(null);
  const [designando, setDesignando] = useState(false);

  const cargar = useCallback(async () => {
    try {
      const { data } = await api.get(`/casos/${caso.id}/pericias`);
      setPericias(data);
    } catch {
      setPericias([]);
    }
  }, [caso.id]);

  useEffect(() => {
    // La carga ocurre después del await: no hay render en cascada.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    cargar();
  }, [cargar]);

  const puedeDesignar = puede(usuario, "gestionar_pericias") && caso.estado !== "cerrado";

  return (
    <div className="bg-surface-container-low rounded-xl p-space-md mb-space-md">
      <div className="flex items-center justify-between mb-space-sm gap-space-md flex-wrap">
        <div>
          <h2 className="font-headline-sm text-headline-sm text-on-surface">Pericias</h2>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            Designación, emisión, traslado, observaciones y absolución (CPP 2004).
          </p>
        </div>
        <div className="flex gap-space-sm">
          {puede(usuario, "ver_padron") && (
            <Link to="/peritos" className={btnSec}><span className="material-symbols-outlined text-base">badge</span>Padrón de peritos</Link>
          )}
          {puedeDesignar && !designando && (
            <button onClick={() => setDesignando(true)} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui">
              <span className="material-symbols-outlined text-base">gavel</span>Designar perito oficial
            </button>
          )}
        </div>
      </div>
      {designando && <FormDesignar caso={caso} onListo={() => { setDesignando(false); cargar(); }} onCancelar={() => setDesignando(false)} />}
      {!pericias ? (
        <p className="font-body-sm text-body-sm text-outline">Cargando...</p>
      ) : pericias.length === 0 ? (
        <p className="font-body-sm text-body-sm text-outline">Aún no se designa ninguna pericia en este caso.</p>
      ) : (
        <div className="flex flex-col gap-space-md">
          {pericias.map((p) => <TarjetaPericia key={p.id} pericia={p} usuario={usuario} onCambio={cargar} />)}
        </div>
      )}
    </div>
  );
}
