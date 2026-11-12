"""Almacenamiento de la evidencia.

Sprint 6 (historia 22): la evidencia puede guardarse en disco local (como hasta el
Sprint 5) o en un bucket S3/MinIO, según STORAGE_BACKEND.

Cada archivo se identifica por su "ruta", que es lo que se guarda en la base de datos:
  - en disco:  storage/<caso>/<hex>/original/<nombre>
  - en S3:     s3://<bucket>/<caso>/<hex>/original/<nombre>
Por eso los archivos subidos antes de pasar a S3 siguen funcionando: su ruta no empieza
por s3:// y se leen del disco.

En S3 el bucket se crea con versionado: si alguien sobrescribe un objeto, la versión
anterior no se pierde y la alerta de integridad (historia 12) lo detecta igual.
"""
import os
import shutil
import uuid
from contextlib import contextmanager
from functools import lru_cache
from urllib.parse import quote

from fastapi.responses import FileResponse, StreamingResponse

from app.core.config import settings

STORAGE_DIR = "storage"
PREFIJO_S3 = "s3://"
CHUNK = 1024 * 1024  # 1 MB


# ---------------------------------------------------------------- S3 / MinIO

def usa_s3() -> bool:
    return settings.STORAGE_BACKEND.lower() == "s3"


@lru_cache(maxsize=1)
def _cliente():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL or None,
        aws_access_key_id=settings.S3_ACCESS_KEY or None,
        aws_secret_access_key=settings.S3_SECRET_KEY or None,
        region_name=settings.S3_REGION,
        # MinIO usa direcciones del tipo http://minio:9000/<bucket>/<clave>
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def _es_s3(ruta: str) -> bool:
    return ruta.startswith(PREFIJO_S3)


def _bucket_y_clave(ruta: str):
    bucket, _, clave = ruta[len(PREFIJO_S3):].partition("/")
    return bucket, clave


def preparar_almacenamiento() -> None:
    """Al arrancar: si se usa S3, crea el bucket (con versionado) si no existe."""
    if not usa_s3():
        return
    cliente = _cliente()
    try:
        cliente.head_bucket(Bucket=settings.S3_BUCKET)
    except Exception:
        cliente.create_bucket(Bucket=settings.S3_BUCKET)
        print(f"[almacenamiento] Bucket '{settings.S3_BUCKET}' creado.", flush=True)
    try:
        cliente.put_bucket_versioning(
            Bucket=settings.S3_BUCKET, VersioningConfiguration={"Status": "Enabled"}
        )
    except Exception as e:  # algunos servicios S3 no permiten versionado: no es fatal
        print(f"[almacenamiento] No se pudo activar el versionado: {e}", flush=True)
    print(f"[almacenamiento] Evidencia en S3: {settings.S3_ENDPOINT_URL or 'AWS'} / {settings.S3_BUCKET}", flush=True)


# ---------------------------------------------------------------- operaciones

def guardar_stream(subruta: str, origen) -> str:
    """Guarda el contenido de `origen` (objeto tipo archivo) en <subruta> y devuelve su ruta."""
    subruta = subruta.replace("\\", "/")
    if usa_s3():
        _cliente().upload_fileobj(origen, settings.S3_BUCKET, subruta)
        return f"{PREFIJO_S3}{settings.S3_BUCKET}/{subruta}"
    ruta = os.path.join(STORAGE_DIR, *subruta.split("/"))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "wb") as destino:
        shutil.copyfileobj(origen, destino)
    return ruta


def copiar(ruta_origen: str, subruta_destino: str) -> str:
    """Copia un archivo ya guardado a otra subruta (en el mismo almacenamiento)."""
    if _es_s3(ruta_origen):
        bucket, clave = _bucket_y_clave(ruta_origen)
        _cliente().copy_object(Bucket=bucket, Key=subruta_destino, CopySource={"Bucket": bucket, "Key": clave})
        return f"{PREFIJO_S3}{bucket}/{subruta_destino}"
    destino = os.path.join(STORAGE_DIR, *subruta_destino.split("/"))
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    shutil.copy2(ruta_origen, destino)
    return destino


def existe(ruta: str) -> bool:
    if not ruta:
        return False
    if _es_s3(ruta):
        bucket, clave = _bucket_y_clave(ruta)
        try:
            _cliente().head_object(Bucket=bucket, Key=clave)
            return True
        except Exception:
            return False
    return os.path.exists(ruta)


def tamano(ruta: str) -> int:
    if _es_s3(ruta):
        bucket, clave = _bucket_y_clave(ruta)
        return _cliente().head_object(Bucket=bucket, Key=clave)["ContentLength"]
    return os.path.getsize(ruta)


@contextmanager
def abrir(ruta: str):
    """Abre el archivo para LECTURA (nunca para escribir)."""
    if _es_s3(ruta):
        bucket, clave = _bucket_y_clave(ruta)
        cuerpo = _cliente().get_object(Bucket=bucket, Key=clave)["Body"]
        try:
            yield cuerpo
        finally:
            cuerpo.close()
    else:
        with open(ruta, "rb") as f:
            yield f


def respuesta_descarga(ruta: str, nombre: str):
    """Respuesta HTTP que entrega el archivo, esté en disco o en S3."""
    if not _es_s3(ruta):
        return FileResponse(ruta, filename=nombre)

    def trozos():
        with abrir(ruta) as f:
            while chunk := f.read(CHUNK):
                yield chunk

    disposicion = f"attachment; filename*=UTF-8''{quote(nombre)}"
    return StreamingResponse(
        trozos(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": disposicion, "Content-Length": str(tamano(ruta))},
    )


def descripcion(ruta: str) -> str:
    """Texto legible de dónde está el archivo (para mostrar en la ficha)."""
    if _es_s3(ruta):
        bucket, _ = _bucket_y_clave(ruta)
        return f"S3 · bucket {bucket}"
    return "Disco local del servidor"


# ---------------------------------------------------------------- evidencia

def guardar_archivo(caso_id: str, nombre_original: str, origen) -> tuple[str, str]:
    """Guarda el original intacto y crea la copia de trabajo.
    Devuelve (ruta_original, ruta_copia_trabajo)."""
    carpeta = f"{caso_id}/{uuid.uuid4().hex}"
    nombre_seguro = os.path.basename((nombre_original or "archivo").replace("\\", "/")) or "archivo"
    ruta_original = guardar_stream(f"{carpeta}/original/{nombre_seguro}", origen)
    ruta_copia = copiar(ruta_original, f"{carpeta}/copia/{nombre_seguro}")
    return ruta_original, ruta_copia
