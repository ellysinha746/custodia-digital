import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import Layout from "../components/Layout";

// Sprint 4 (historia 18): dashboard de métricas del administrador.

const ESPECIALIDADES = {
  audio: "Audio",
  video: "Video",
  informatica: "Informática",
  telefonia: "Telefonía",
};

const TIPO_ALERTA = {
  hash_sin_respaldo: "Hash sin respaldo",
  dispositivo_sustituido: "Dispositivo sustituido",
};

function formatoHoras(h) {
  if (h === null || h === undefined) return "—";
  if (h < 24) return `${h} h`;
  return `${(h / 24).toFixed(1)} días`;
}

function Tile({ icono, valor, etiqueta, detalle, alerta }) {
  return (
    <div className="bg-surface-container-low rounded-xl p-space-md flex items-start gap-space-md">
      <div
        className={`w-11 h-11 rounded-lg flex items-center justify-center ${
          alerta ? "bg-error/10 text-error" : "bg-surface-container-high text-primary"
        }`}
      >
        <span className="material-symbols-outlined">{icono}</span>
      </div>
      <div>
        <div className="font-headline-lg text-headline-lg text-on-surface leading-none">{valor}</div>
        <div className="mt-1.5 font-label-ui text-label-ui text-outline uppercase tracking-wider">{etiqueta}</div>
        {detalle && <div className="mt-1 font-body-sm text-body-sm text-on-surface-variant">{detalle}</div>}
      </div>
    </div>
  );
}

/** Lista con barras proporcionales de un solo tono (magnitud, no identidad). */
function Desglose({ titulo, filas }) {
  const max = Math.max(1, ...filas.map((f) => f.valor));
  return (
    <div className="bg-surface-container-low rounded-xl p-space-md">
      <h2 className="font-headline-sm text-headline-sm text-on-surface mb-space-sm">{titulo}</h2>
      <ul className="flex flex-col gap-2.5">
        {filas.map((f) => (
          <li key={f.etiqueta}>
            <div className="flex justify-between font-body-sm text-body-sm mb-1">
              <span className="text-on-surface-variant">{f.etiqueta}</span>
              <span className="text-on-surface font-semibold">{f.valor}</span>
            </div>
            <div className="h-1.5 bg-surface-container-high rounded-full overflow-hidden">
              <div className="h-full bg-primary rounded-full" style={{ width: `${(f.valor / max) * 100}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Barras verticales de una sola serie con tooltip al pasar el mouse. */
function GraficoActividad({ datos }) {
  const [activo, setActivo] = useState(null);
  const max = Math.max(1, ...datos.map((d) => d.eventos));
  const etiquetaDia = (iso) =>
    new Date(`${iso}T12:00:00`).toLocaleDateString("es-PE", { day: "2-digit", month: "short" });

  return (
    <div className="bg-surface-container-low rounded-xl p-space-md">
      <div className="flex items-baseline justify-between mb-space-sm">
        <h2 className="font-headline-sm text-headline-sm text-on-surface">Eventos de custodia por día</h2>
        <span className="font-label-code-sm text-label-code-sm text-outline">últimos 14 días</span>
      </div>
      <div className="relative h-48 flex items-end gap-[2px] border-b border-outline-variant/40">
        {datos.map((d, i) => (
          <div
            key={d.fecha}
            className="flex-1 h-full flex items-end cursor-default"
            onMouseEnter={() => setActivo(i)}
            onMouseLeave={() => setActivo(null)}
          >
            <div
              className={`w-full rounded-t ${activo === i ? "bg-primary" : "bg-primary/70"}`}
              style={{ height: `${(d.eventos / max) * 100}%`, minHeight: d.eventos ? 4 : 0 }}
            />
          </div>
        ))}
        {activo !== null && (
          <div
            className={`absolute -top-2 -translate-y-full ${
              activo < 2 ? "translate-x-0" : activo > datos.length - 3 ? "-translate-x-full" : "-translate-x-1/2"
            } bg-surface-container-high border border-outline-variant/30 rounded-md px-2.5 py-1.5 shadow-xl pointer-events-none whitespace-nowrap`}
            style={{ left: `${((activo + 0.5) / datos.length) * 100}%` }}
          >
            <div className="font-label-code-sm text-label-code-sm text-outline">{etiquetaDia(datos[activo].fecha)}</div>
            <div className="font-body-sm text-body-sm text-on-surface">
              {datos[activo].eventos} evento(s) · {datos[activo].alertas} alerta(s)
            </div>
          </div>
        )}
      </div>
      <div className="flex justify-between mt-1.5 font-label-code-sm text-label-code-sm text-outline">
        <span>{etiquetaDia(datos[0].fecha)}</span>
        <span>{etiquetaDia(datos[datos.length - 1].fecha)}</span>
      </div>
      <table className="sr-only">
        <caption>Eventos y alertas por día</caption>
        <tbody>
          {datos.map((d) => (
            <tr key={d.fecha}>
              <td>{d.fecha}</td>
              <td>{d.eventos} eventos</td>
              <td>{d.alertas} alertas</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Dashboard() {
  const [m, setM] = useState(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    api
      .get("/metricas")
      .then(({ data }) => setM(data))
      .catch((err) => {
        if (err.response?.status === 401) {
          localStorage.clear();
          navigate("/");
        } else {
          setError(err.response?.data?.detail || "No se pudieron cargar las métricas.");
        }
      });
  }, [navigate]);

  return (
    <Layout>
      <div className="mb-space-lg">
        <h1 className="font-headline-lg text-headline-lg text-on-surface">Dashboard</h1>
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          Salud general del sistema de custodia
          {m ? ` · actualizado ${new Date(m.generado_en).toLocaleTimeString("es-PE")}` : ""}
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-2 bg-error/10 border border-error/30 rounded-lg px-space-md py-3 text-error font-body-sm text-body-sm">
          <span className="material-symbols-outlined">lock</span>
          {error}
        </div>
      )}

      {!m && !error && <p className="font-body-md text-body-md text-on-surface-variant">Cargando métricas...</p>}

      {m && (
        <div className="flex flex-col gap-space-md">
          <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-space-md">
            <Tile
              icono="folder_open"
              valor={m.casos_abiertos + m.casos_en_proceso}
              etiqueta="Casos activos"
              detalle={`${m.casos_abiertos} abiertos · ${m.casos_en_proceso} en proceso`}
            />
            <Tile
              icono="gpp_maybe"
              valor={m.alertas_total}
              etiqueta="Alertas generadas"
              detalle={`${m.alertas_pendientes} pendientes · ${m.alertas_atendidas} atendidas`}
              alerta={m.alertas_pendientes > 0}
            />
            <Tile
              icono="timer"
              valor={formatoHoras(m.tiempo_promedio_cierre_horas)}
              etiqueta="Tiempo promedio de cierre"
              detalle={
                m.casos_cierre_medido
                  ? `sobre ${m.casos_cierre_medido} caso(s) cerrado(s)`
                  : "aún no hay casos cerrados con fecha registrada"
              }
            />
            <Tile
              icono="description"
              valor={m.archivos_total}
              etiqueta="Evidencias en custodia"
              detalle={`${m.verificaciones_total} verificaciones realizadas`}
            />
          </div>

          <GraficoActividad datos={m.actividad} />

          <div className="grid md:grid-cols-3 gap-space-md">
            <Desglose
              titulo="Casos por estado"
              filas={[
                { etiqueta: "Abiertos", valor: m.casos_abiertos },
                { etiqueta: "En proceso", valor: m.casos_en_proceso },
                { etiqueta: "Cerrados", valor: m.casos_cerrados },
                { etiqueta: "En papelera", valor: m.casos_en_papelera },
              ]}
            />
            <Desglose
              titulo="Casos por especialidad"
              filas={Object.entries(ESPECIALIDADES).map(([k, v]) => ({
                etiqueta: v,
                valor: m.casos_por_especialidad[k] || 0,
              }))}
            />
            <Desglose
              titulo="Alertas por tipo"
              filas={Object.entries(TIPO_ALERTA).map(([k, v]) => ({
                etiqueta: v,
                valor: m.alertas_por_tipo[k] || 0,
              }))}
            />
          </div>
        </div>
      )}
    </Layout>
  );
}