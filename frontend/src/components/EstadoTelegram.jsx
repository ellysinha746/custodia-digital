import { useEffect, useState } from "react";
import api from "../api";
import { useToast } from "./Toast";

// Sprint 7 (historia 33): estado del bot de Telegram y mensaje de prueba.
export default function EstadoTelegram() {
  const [activo, setActivo] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const { notificar } = useToast();

  useEffect(() => {
    api
      .get("/telegram/estado")
      .then(({ data }) => setActivo(data.activo))
      .catch(() => setActivo(false));
  }, []);

  const probar = async () => {
    setEnviando(true);
    try {
      const { data } = await api.post("/telegram/prueba");
      notificar(data.enviado ? "Mensaje de prueba enviado al grupo de Telegram." : "Telegram no aceptó el mensaje.", {
        tipo: data.enviado ? "success" : "error",
      });
    } catch {
      notificar("No se pudo enviar el mensaje de prueba.", { tipo: "error" });
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="bg-surface-container-low rounded-xl px-space-md py-3 flex flex-wrap items-center justify-between gap-space-sm">
      <div className="flex items-center gap-space-sm">
        <span className="material-symbols-outlined text-primary">send</span>
        <div>
          <h2 className="font-headline-sm text-headline-sm text-on-surface">Alertas por Telegram</h2>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            {activo === null
              ? "Revisando..."
              : activo
              ? "Conectado: las alertas de integridad y los plazos por vencer también llegan al grupo del laboratorio."
              : "Desactivado: falta configurar TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en el servidor."}
          </p>
        </div>
      </div>
      {activo && (
        <button
          onClick={probar}
          disabled={enviando}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-on-primary font-label-ui text-label-ui disabled:opacity-60"
        >
          <span className="material-symbols-outlined text-base">send</span>
          {enviando ? "Enviando..." : "Enviar mensaje de prueba"}
        </button>
      )}
    </div>
  );
}