// Sprint 6 (historia 25): marco común del login y de "Solicitar acceso".
export default function PantallaAcceso({ titulo, subtitulo, ancho = "max-w-md", children }) {
  return (
    <div className="min-h-screen bg-surface flex items-center justify-center px-4 py-10">
      <div className={`w-full ${ancho} flex flex-col gap-space-lg`}>
        <div className="flex items-center gap-space-md">
          <div className="w-11 h-11 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
            <span className="material-symbols-outlined">shield_lock</span>
          </div>
          <div className="flex flex-col">
            <span className="font-headline-sm text-headline-sm tracking-tight text-on-surface">CustodiaDigital</span>
            <span className="font-label-code-sm text-label-code-sm text-outline uppercase tracking-wider">
              Cadena de Custodia Forense
            </span>
          </div>
        </div>
        <div className="bg-surface-container-low rounded-xl p-space-lg flex flex-col gap-space-md border border-outline-variant/30">
          <div>
            <h1 className="font-headline-md text-headline-md text-on-surface">{titulo}</h1>
            {subtitulo && <p className="font-body-sm text-body-sm text-on-surface-variant mt-1">{subtitulo}</p>}
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}

export const claseCampo =
  "w-full px-3 py-2.5 rounded-md bg-surface-container-lowest text-on-surface font-body-sm text-body-sm border border-outline-variant/40 focus:outline-none focus:ring-1 focus:ring-primary/60";