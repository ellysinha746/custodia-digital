import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api from "../api";
import { limpiarSesion } from "../sesion";
import Layout from "../components/Layout";

// Sprint 5 (historia 19.9): perfil del perito — su carga de trabajo.
// /perfil → el propio perito; /peritos/:id → el jefe o el fiscal viendo a otro perito.

const ESPECIALIDADES = { audio: "Audio", video: "Video", informatica: "Informática", telefonia: "Telefonía" };

function fecha(iso) {
  return iso ? new Date(iso).toLocaleString("es-PE", { dateStyle: "medium", timeStyle: "short" }) : "—";
}

function Lista({ titulo, icono, items, vacio, detalle, tono }) {
  const navigate = useNavigate();
  return (
    <div className="bg-surface-container-low rounded-xl p-space-md">
      <h2 className="font-headline-sm text-headline-sm text-on-surface mb-space-sm flex items-center gap-2">
        <span className={`material-symbols-outlined ${tono || "text-primary"}`}>{icono}</span>
        {titulo} <span className="text-outline font-label-code-sm text-label-code-sm">({items.length})</span>
      </h2>
      {items.length === 0 ? (
        <p className="font-body-sm text-body-sm text-outline">{vacio}</p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {items.map((p, i) => (
            <li key={`${p.id || p.codigo}-${i}`}>
              <button onClick={() => navigate(`/casos/${p.caso_id}`)} className="w-full text-left px-2.5 py-2 rounded-lg hover:bg-surface-container font-body-sm text-body-sm">
                <span className="font-label-code-sm text-label-code-sm text-primary">{p.codigo}</span>
                <span className="text-on-surface"> · Caso {p.caso_numero}</span>
                <div className="text-on-surface-variant">{detalle(p)}</div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function PerfilPerito() {
  const { id } = useParams();
  const [perfil, setPerfil] = useState(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    let activo = true;
    api
      .get(id ? `/peritos/${id}/perfil` : "/perfil")
      .then(({ data }) => activo && setPerfil(data))
      .catch((err) => {
        if (err.response?.status === 401) {
          limpiarSesion();
          navigate("/");
        } else if (activo) setError(err.response?.data?.detail || "No se pudo cargar el perfil.");
      });
    return () => {
      activo = false;
    };
  }, [id, navigate]);

  if (error) {
    return (
      <Layout>
        <p className="text-error font-body-md text-body-md">{error}</p>
      </Layout>
    );
  }
  if (!perfil) {
    return (
      <Layout>
        <p className="font-body-md text-body-md text-on-surface-variant">Cargando perfil...</p>
      </Layout>
    );
  }

  const p = perfil.perito;
  return (
    <Layout>
      <div className="bg-surface-container-low rounded-xl p-space-md mb-space-md flex items-start justify-between gap-space-md flex-wrap">
        <div className="flex items-start gap-space-md">
          <div className="w-14 h-14 rounded-full bg-primary/15 text-primary ring-1 ring-primary/30 flex items-center justify-center font-headline-sm text-headline-sm">
            {p.nombre.split(" ").map((x) => x[0]).slice(0, 2).join("").toUpperCase()}
          </div>
          <div>
            <h1 className="font-headline-lg text-headline-lg text-on-surface">{p.nombre}</h1>
            <p className="font-body-sm text-body-sm text-on-surface-variant">
              {p.tipo_etiqueta} · {ESPECIALIDADES[p.especialidad]} · {p.institucion || "sin institución"}
            </p>
            <p className="font-label-code-sm text-label-code-sm text-outline">
              {p.registro_profesional || "sin N° de registro"} · {p.email}{p.telefono ? ` · ${p.telefono}` : ""}
            </p>
          </div>
        </div>
        <span className={`font-label-ui text-label-ui ${p.habilitado ? "text-tertiary" : "text-error"}`}>
          {p.habilitado ? "Habilitado" : "Inhabilitado"}
        </span>
      </div>

      <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-space-md mb-space-md">
        {[
          { v: p.pericias_activas, t: "Pericias activas", i: "work" },
          { v: perfil.por_absolver.length, t: "Observaciones por absolver", i: "task", alerta: perfil.por_absolver.length > 0 },
          { v: perfil.plazos_por_vencer.length, t: "Plazos por vencer", i: "timer", alerta: perfil.plazos_por_vencer.length > 0 },
          { v: perfil.subrogaciones.length, t: "Subrogaciones", i: "swap_horiz" },
        ].map((k) => (
          <div key={k.t} className="bg-surface-container-low rounded-xl p-space-md flex items-center gap-space-md">
            <div className={`w-11 h-11 rounded-lg flex items-center justify-center ${k.alerta ? "bg-error/10 text-error" : "bg-surface-container-high text-primary"}`}>
              <span className="material-symbols-outlined">{k.i}</span>
            </div>
            <div>
              <div className="font-headline-lg text-headline-lg text-on-surface leading-none">{k.v}</div>
              <div className="mt-1 font-label-ui text-label-ui text-outline uppercase tracking-wider">{k.t}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid md:grid-cols-2 gap-space-md mb-space-md">
        {p.tipo === "perito" ? (
          <Lista titulo="Observaciones por absolver" icono="task" tono="text-error" items={perfil.por_absolver}
            vacio="No tienes observaciones pendientes." detalle={(x) => `${x.observaciones_pendientes} observación(es) pendiente(s)`} />
        ) : (
          <Lista titulo="Pericias en traslado (puedes observar)" icono="rate_review" items={perfil.por_observar}
            vacio="No hay pericias en traslado." detalle={(x) => `Traslado vence ${fecha(x.traslado_vence_en)}`} />
        )}
        <Lista titulo="Plazos por vencer" icono="timer" tono="text-amber-400" items={perfil.plazos_por_vencer}
          vacio="Sin plazos por vencer en los próximos 3 días." detalle={(x) => x.alerta} />
      </div>

      <div className="bg-surface-container-low rounded-xl overflow-hidden mb-space-md">
        <div className="px-space-md py-3 border-b border-outline-variant/20 flex items-center justify-between">
          <h2 className="font-headline-sm text-headline-sm text-on-surface">Pericias asignadas</h2>
          <span className="font-label-code-sm text-label-code-sm text-outline">
            {Object.entries(perfil.pericias_por_estado).map(([k, v]) => `${k}: ${v}`).join(" · ") || "ninguna"}
          </span>
        </div>
        <table className="w-full text-left">
          <thead>
            <tr className="bg-surface-container-lowest">
              {["Pericia", "Caso", "Participa como", "Estado", "Vence"].map((h) => (
                <th key={h} className="px-space-md py-2.5 font-label-ui text-label-ui text-outline uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {perfil.pericias.map((x) => (
              <tr key={x.id} onClick={() => navigate(`/casos/${x.caso_id}`)} className="border-t border-outline-variant/20 cursor-pointer hover:bg-surface-container">
                <td className="px-space-md py-2.5 font-label-code-sm text-label-code-sm text-primary">{x.codigo}</td>
                <td className="px-space-md py-2.5 font-label-code-sm text-label-code-sm text-on-surface">{x.caso_numero}</td>
                <td className="px-space-md py-2.5 font-body-sm text-body-sm text-on-surface-variant">{x.rol_en_pericia === "oficial" ? "Perito oficial" : "Perito de parte"}</td>
                <td className="px-space-md py-2.5 font-body-sm text-body-sm text-on-surface">{x.estado_etiqueta}</td>
                <td className={`px-space-md py-2.5 font-label-code-sm text-label-code-sm ${x.alerta ? "text-error" : "text-outline"}`}>
                  {x.estado === "designada" ? fecha(x.fecha_limite) : x.traslado_vence_en ? fecha(x.traslado_vence_en) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {perfil.pericias.length === 0 && <p className="py-8 text-center font-body-sm text-body-sm text-outline">Sin pericias asignadas.</p>}
      </div>

      {perfil.subrogaciones.length > 0 && (
        <div className="bg-surface-container-low rounded-xl p-space-md">
          <h2 className="font-headline-sm text-headline-sm text-on-surface mb-space-sm">Pericias donde fue subrogado</h2>
          <ul className="flex flex-col gap-1.5 font-body-sm text-body-sm">
            {perfil.subrogaciones.map((s, i) => (
              <li key={i} className="text-on-surface-variant">
                <span className="font-label-code-sm text-label-code-sm text-outline">{s.codigo}</span> · Caso {s.caso_numero} · {fecha(s.subrogado_en)} · {s.motivo} · {s.documento}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Layout>
  );
}
