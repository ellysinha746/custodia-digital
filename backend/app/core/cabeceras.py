"""Sprint 6 (historia 27): cabeceras de seguridad HTTP en todas las respuestas de la API.

- Content-Security-Policy: la API solo devuelve datos (JSON, PDF, CSV), así que no se le
  permite cargar NADA ni mostrarse dentro de un iframe. Swagger (/docs) necesita sus
  scripts del CDN, por eso tiene una política aparte, igual de cerrada para iframes.
- X-Frame-Options: DENY → nadie puede incrustar la API en otra página (clickjacking).
- X-Content-Type-Options: nosniff → el navegador no "adivina" el tipo de un archivo:
  una evidencia descargada nunca se ejecuta como script o HTML.
- Referrer-Policy: no-referrer → las URLs (con IDs de casos) no se filtran a otros sitios.
- Permissions-Policy → la API no pide cámara, micrófono, ubicación ni pagos.
- Cache-Control: no-store → datos de casos y tokens no quedan en la caché del navegador
  ni de proxies.
- Strict-Transport-Security: solo cuando se sirve por HTTPS (en local es HTTP).
"""
from fastapi import Request

CSP_API = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
CSP_DOCS = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.redoc.ly; "
    "worker-src blob:; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)
RUTAS_DOCS = ("/docs", "/redoc", "/openapi.json")

CABECERAS_FIJAS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


async def cabeceras_seguridad(request: Request, call_next):
    respuesta = await call_next(request)
    ruta = request.url.path
    es_docs = ruta.startswith(RUTAS_DOCS)
    for nombre, valor in CABECERAS_FIJAS.items():
        respuesta.headers.setdefault(nombre, valor)
    respuesta.headers.setdefault("Content-Security-Policy", CSP_DOCS if es_docs else CSP_API)
    if not es_docs:
        respuesta.headers.setdefault("Cache-Control", "no-store")
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    if proto == "https":
        respuesta.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return respuesta
