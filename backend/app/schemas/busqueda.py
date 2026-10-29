from pydantic import BaseModel
from typing import List

from app.schemas.caso import CasoOut
from app.schemas.archivo import ArchivoOut


class ArchivoBusquedaOut(ArchivoOut):
    caso_numero: str


class BusquedaOut(BaseModel):
    casos: List[CasoOut]
    archivos: List[ArchivoBusquedaOut]
