import hashlib
import re

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


# ---------------------------------------------------------------------------
# Sprint 6 (historia 23): doble hash y cotejo con herramientas forenses.

def calcular_hashes(ruta: str) -> dict:
    """SHA-256, SHA-1 y MD5 en UNA sola lectura del archivo (importa con evidencia
    de varios GB). SHA-1 y MD5 ya no sirven solos como garantía, pero los informes de
    Cellebrite y FTK los traen, así que se guardan para poder cotejar."""
    h = {
        "sha256": hashlib.sha256(),
        "sha1": hashlib.sha1(usedforsecurity=False),
        "md5": hashlib.md5(usedforsecurity=False),
    }
    with abrir(ruta) as f:
        while chunk := f.read(CHUNK_SIZE):
            for algoritmo in h.values():
                algoritmo.update(chunk)
    return {nombre: algoritmo.hexdigest() for nombre, algoritmo in h.items()}


ALGORITMO_POR_LARGO = {32: "md5", 40: "sha1", 64: "sha256"}
ETIQUETA_ALGORITMO = {"md5": "MD5", "sha1": "SHA-1", "sha256": "SHA-256"}

# Una "palabra" hexadecimal de exactamente 32, 40 o 64 caracteres (no un trozo de una más larga).
_PATRON_HASH = re.compile(r"(?<![0-9A-Fa-f])([0-9A-Fa-f]{64}|[0-9A-Fa-f]{40}|[0-9A-Fa-f]{32})(?![0-9A-Fa-f])")


def extraer_hashes(texto: str) -> list:
    """Saca los MD5, SHA-1 y SHA-256 de un texto pegado: un hash suelto o el bloque
    del informe ("MD5 checksum: 9e107d9d...", "SHA256: ..."). Sin repetir y en orden."""
    vistos, hashes = set(), []
    for valor in _PATRON_HASH.findall(texto or ""):
        valor = valor.lower()
        if valor not in vistos:
            vistos.add(valor)
            hashes.append({"algoritmo": ALGORITMO_POR_LARGO[len(valor)], "valor": valor})
    return hashes
