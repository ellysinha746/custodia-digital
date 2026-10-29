import hashlib

CHUNK_SIZE = 1024 * 1024  # 1 MB


def calcular_sha256(ruta: str) -> str:
    sha256 = hashlib.sha256()
    with open(ruta, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            sha256.update(chunk)
    return sha256.hexdigest()


def verificar_integridad(ruta: str, hash_esperado: str) -> bool:
    return calcular_sha256(ruta) == hash_esperado