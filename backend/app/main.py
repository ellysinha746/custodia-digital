import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, casos, archivos, auditoria, busqueda, alertas, fichas
from app.core.config import settings
from app.services.integridad_service import escanear_todos, notificar_alerta


async def _bucle_escaneo_integridad():
    """Sprint 4 (historia 12): revisa la integridad de todos los archivos
    cada ESCANEO_INTEGRIDAD_MIN minutos, sin que nadie lo pida."""
    while True:
        await asyncio.sleep(settings.ESCANEO_INTEGRIDAD_MIN * 60)
        try:
            revisados, nuevas = await asyncio.to_thread(escanear_todos)
            for alerta_id in nuevas:
                await asyncio.to_thread(notificar_alerta, alerta_id)
            print(f"[escaneo] {revisados} archivo(s) revisados, {len(nuevas)} alerta(s) nuevas", flush=True)
        except Exception as e:
            print(f"[escaneo] Error: {e}", flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tarea = asyncio.create_task(_bucle_escaneo_integridad())
    yield
    tarea.cancel()


app = FastAPI(title="Cadena de Custodia - API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(casos.router)
app.include_router(archivos.router)
app.include_router(auditoria.router)
app.include_router(busqueda.router)
app.include_router(alertas.router)
app.include_router(fichas.router)

@app.get("/")
def root():
    return {"status": "ok"}