import hashlib

from app.services.storage_service import abrir

CHUNK_SIZE = 1024 * 1024  # 1 MB


def calcular_sha256(ruta: str) -> str:
    sha256 = hashlib.sha256()
    with abrir(ruta) as f:  # Sprint 6: funciona en disco y en S3/MinIO
        while chunk := f.read(CHUNK_SIZE):
            sha256.update(chunk)
    return sha256.hexdigest()


def verificar_integridad(ruta: str, hash_esperado: str) -> bool:
    return calcular_sha256(ruta) == hash_esperado