import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, casos, archivos, auditoria, busqueda, alertas, fichas, observadas, reportes, metricas, usuarios, peritos, pericias, recordatorios
from app.core.config import settings
from app.services.integridad_service import escanear_todos, notificar_alerta
from app.services.recordatorio_service import enviar_recordatorios
from app.services.storage_service import preparar_almacenamiento


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


async def _bucle_recordatorios():
    """Sprint 6 (historia 26): revisa los plazos de las pericias cada
    RECORDATORIOS_CADA_MIN minutos y avisa los que están por vencer."""
    while True:
        try:
            enviados = await asyncio.to_thread(enviar_recordatorios)
            if enviados:
                print(f"[recordatorios] {enviados} recordatorio(s) de plazo enviados", flush=True)
        except Exception as e:
            print(f"[recordatorios] Error: {e}", flush=True)
        await asyncio.sleep(settings.RECORDATORIOS_CADA_MIN * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await asyncio.to_thread(preparar_almacenamiento)  # Sprint 6 (historia 22)
    except Exception as e:
        print(f"[almacenamiento] No se pudo preparar el bucket S3: {e}", flush=True)
    tareas = [
        asyncio.create_task(_bucle_escaneo_integridad()),
        asyncio.create_task(_bucle_recordatorios()),
    ]
    yield
    for tarea in tareas:
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
app.include_router(observadas.router)
app.include_router(reportes.router)
app.include_router(metricas.router)
app.include_router(usuarios.router)
app.include_router(peritos.router)
app.include_router(pericias.router)
app.include_router(recordatorios.router)

@app.get("/")
def root():
    return {"status": "ok"}