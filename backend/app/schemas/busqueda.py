from pydantic import BaseModel
from typing import List, Optional

from app.schemas.caso import CasoOut
from app.schemas.archivo import ArchivoOut


class ArchivoBusquedaOut(ArchivoOut):
    caso_numero: str
    fragmento_texto: Optional[str] = None  # Sprint 7 (historia 29): dónde aparece en el texto OCR


class BusquedaOut(BaseModel):
    casos: List[CasoOut]
    archivos: List[ArchivoBusquedaOut]
