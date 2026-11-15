import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Sprint 6 (historia 27): cabeceras de seguridad de la PÁGINA.
// La CSP solo deja cargar scripts propios, las fuentes de Google y hablar con la API.
// En desarrollo Vite necesita 'unsafe-inline' (script de recarga en caliente) y su websocket;
// el build de producción (`npm run preview`) va sin 'unsafe-inline' en los scripts.
const API = 'http://localhost:8000'

function csp(desarrollo) {
  return [
    "default-src 'self'",
    `script-src 'self'${desarrollo ? " 'unsafe-inline'" : ''}`,
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: blob:",
    `connect-src 'self' ${API}${desarrollo ? ' ws://localhost:5173' : ''}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join('; ')
}

const cabeceras = (desarrollo) => ({
  'Content-Security-Policy': csp(desarrollo),
  'X-Frame-Options': 'DENY',
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=(), usb=()',
})

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: { headers: cabeceras(true) },
  preview: { headers: cabeceras(false) },
})
