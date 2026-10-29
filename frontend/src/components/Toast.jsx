import { createContext, useCallback, useContext, useRef, useState } from "react";

const ToastContext = createContext(null);

const ICONS = {
  info: "info",
  success: "check_circle",
  error: "error",
};

const COLORS = {
  info: "text-secondary",
  success: "text-tertiary",
  error: "text-error",
};

let permisoSolicitado = false;

function pedirPermisoNotificacion() {
  if (permisoSolicitado) return;
  permisoSolicitado = true;
  if (typeof Notification !== "undefined" && Notification.permission === "default") {
    Notification.requestPermission().catch(() => {});
  }
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const idRef = useRef(0);

  const notificar = useCallback((mensaje, { tipo = "info", sistemaOperativo = false, titulo } = {}) => {
    const id = ++idRef.current;
    setToasts((prev) => [...prev, { id, mensaje, tipo }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);

    if (sistemaOperativo && typeof Notification !== "undefined" && Notification.permission === "granted") {
      try {
        new Notification(titulo || "CustodiaDigital", { body: mensaje });
      } catch {
        // algunos navegadores en segundo plano rechazan la notificación; el toast ya se mostró
      }
    }
  }, []);

  return (
    <ToastContext.Provider value={{ notificar, pedirPermisoNotificacion }}>
      {children}
      <div className="fixed bottom-6 right-6 z-[100] flex flex-col gap-2 w-80">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="flex items-start gap-2.5 bg-surface-container-high border border-outline-variant/30 rounded-lg px-4 py-3 shadow-2xl animate-[fadeIn_0.15s_ease-out]"
          >
            <span className={`material-symbols-outlined text-xl ${COLORS[t.tipo]}`}>
              {ICONS[t.tipo]}
            </span>
            <p className="font-body-sm text-body-sm text-on-surface flex-1">{t.mensaje}</p>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast debe usarse dentro de <ToastProvider>");
  return ctx;
}
