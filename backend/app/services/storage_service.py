import os
import shutil
import uuid

STORAGE_DIR = "storage"


def guardar_archivo(caso_id: str, nombre_original: str, origen) -> tuple[str, str]:
    """Guarda el original intacto y crea la copia de trabajo.
    Devuelve (ruta_original, ruta_copia_trabajo)."""
    carpeta = os.path.join(STORAGE_DIR, caso_id, uuid.uuid4().hex)
    os.makedirs(os.path.join(carpeta, "original"), exist_ok=True)
    os.makedirs(os.path.join(carpeta, "copia"), exist_ok=True)

    nombre_seguro = os.path.basename(nombre_original)
    ruta_original = os.path.join(carpeta, "original", nombre_seguro)
    ruta_copia = os.path.join(carpeta, "copia", nombre_seguro)

    with open(ruta_original, "wb") as destino:
        shutil.copyfileobj(origen, destino)

    shutil.copy2(ruta_original, ruta_copia)

    return ruta_original, ruta_copia