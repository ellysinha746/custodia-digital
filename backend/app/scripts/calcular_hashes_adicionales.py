"""Sprint 6 (historia 23): calcula SHA-1 y MD5 de toda la evidencia subida antes de esta historia.

Lee cada ORIGINAL una sola vez y solo guarda los hashes nuevos si su SHA-256 sigue siendo
el registrado (si no, lo informa: esa evidencia debe revisarse en Alertas).

Uso (con docker):
    docker compose exec api python -m app.scripts.calcular_hashes_adicionales
"""
from fastapi import HTTPException

from app.db.session import SessionLocal
from app.models.archivo import Archivo, EstadoProcesamientoEnum
from app.services.cotejo_service import asegurar_hashes_adicionales
import app.main  # noqa: F401  (carga todos los modelos)


def main() -> None:
    db = SessionLocal()
    calculados, con_problemas = 0, []
    try:
        pendientes = (
            db.query(Archivo)
            .filter(
                Archivo.estado_procesamiento == EstadoProcesamientoEnum.listo,
                Archivo.hash_original.isnot(None),
                (Archivo.hash_sha1.is_(None)) | (Archivo.hash_md5.is_(None)),
            )
            .all()
        )
        for archivo in pendientes:
            try:
                if asegurar_hashes_adicionales(archivo):
                    db.commit()
                    calculados += 1
            except HTTPException as e:
                db.rollback()
                con_problemas.append(f"{archivo.nombre_original} ({archivo.id}): {e.detail}")
        print(f"[hashes] {calculados} de {len(pendientes)} archivo(s) con SHA-1 y MD5 calculados.")
        for linea in con_problemas:
            print(f"[hashes] NO se calculó → {linea}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
