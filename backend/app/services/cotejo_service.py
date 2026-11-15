"""Sprint 6 (historia 23): doble hash y cotejo con herramientas forenses (Cellebrite, FTK...).

El perito pega el hash (o el bloque de hashes) del informe de la herramienta con la que
hizo la extracción, y el sistema lo compara con los hashes de la evidencia que custodia.
Si ninguno coincide, la evidencia del sistema no es la que procesó la herramienta → alerta.
"""
from datetime import datetime, timezone
from typing import Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.alerta import Alerta
from app.models.archivo import Archivo
from app.services.hashing_service import calcular_hashes, extraer_hashes, ETIQUETA_ALGORITMO
from app.services.storage_service import existe


def asegurar_hashes_adicionales(archivo: Archivo) -> bool:
    """Calcula SHA-1 y MD5 de evidencia subida antes de la historia 23, leyendo el ORIGINAL.
    Solo si su SHA-256 sigue siendo el registrado: no se sacan hashes "válidos" de una
    evidencia alterada. Devuelve True si los calculó ahora (no hace commit)."""
    if archivo.hash_sha1 and archivo.hash_md5:
        return False
    if not archivo.hash_original:
        raise HTTPException(status_code=409, detail="El archivo aún no tiene un hash original calculado.")
    if not existe(archivo.ruta_original):
        raise HTTPException(status_code=404, detail="El original ya no está en el almacenamiento.")
    hashes = calcular_hashes(archivo.ruta_original)
    if hashes["sha256"] != archivo.hash_original:
        raise HTTPException(
            status_code=409,
            detail="El original ya no coincide con su SHA-256 registrado: no se calculan hashes nuevos "
                   "sobre evidencia alterada. Verifica la integridad y revisa las alertas.",
        )
    archivo.hash_sha1 = hashes["sha1"]
    archivo.hash_md5 = hashes["md5"]
    return True


def _esperado(archivo: Archivo, algoritmo: str) -> str:
    return {"sha256": archivo.hash_original, "sha1": archivo.hash_sha1, "md5": archivo.hash_md5}[algoritmo]


def cotejar(
    db: Session, archivo: Archivo, usuario, herramienta: str, texto: str, referencia: Optional[str]
) -> Tuple[dict, Optional[Alerta]]:
    """Compara los hashes del texto con los de la evidencia. No hace commit."""
    encontrados = extraer_hashes(texto)
    if not encontrados:
        raise HTTPException(
            status_code=400,
            detail="No encontré ningún hash en el texto: pega un MD5 (32 caracteres), SHA-1 (40) "
                   "o SHA-256 (64) tal como aparece en el informe.",
        )
    asegurar_hashes_adicionales(archivo)

    herramienta = herramienta.strip()
    referencia = (referencia or "").strip() or None
    resultados = []
    for h in encontrados:
        esperado = _esperado(archivo, h["algoritmo"])
        resultados.append({**h, "esperado": esperado, "coincide": h["valor"] == esperado})

    aciertos = sum(r["coincide"] for r in resultados)
    if aciertos == len(resultados):
        resultado = "coincide"
        algoritmos = ", ".join(dict.fromkeys(ETIQUETA_ALGORITMO[r["algoritmo"]] for r in resultados))
        mensaje = f"Coincide: el {algoritmos} de {herramienta} es igual al de la evidencia custodiada."
    elif aciertos:
        resultado = "parcial"
        mensaje = (
            f"{aciertos} de {len(resultados)} hashes coinciden. Los que no, probablemente son de otros "
            "elementos del informe; revisa que estés comparando el mismo archivo."
        )
    else:
        resultado = "no_coincide"
        mensaje = (
            f"Ningún hash de {herramienta} coincide con la evidencia custodiada: no es el mismo archivo "
            "que procesó la herramienta. El jefe de laboratorio verá la alerta."
        )

    ahora = datetime.now(timezone.utc)
    registro = {
        "fecha": ahora.isoformat(),
        "usuario_id": str(usuario.id),
        "usuario": usuario.nombre,
        "herramienta": herramienta,
        "referencia": referencia,
        "resultado": resultado,
        "hashes": resultados,
    }
    archivo.cotejos = [*(archivo.cotejos or []), registro]  # lista nueva: SQLAlchemy detecta el cambio

    alerta = None
    if resultado == "no_coincide":
        alerta = _alerta_cotejo(db, archivo, resultados[0], herramienta, referencia)

    return {
        "resultado": resultado,
        "mensaje": mensaje,
        "herramienta": herramienta,
        "referencia": referencia,
        "hashes": resultados,
        "alerta_id": alerta.id if alerta else None,
        "cotejado_en": ahora,
    }, alerta


def _alerta_cotejo(db: Session, archivo: Archivo, r: dict, herramienta: str, referencia: Optional[str]):
    # Una sola alerta de cotejo pendiente por archivo: si no, alguien con permiso de cotejar
    # podría llenar Alertas (y el correo de los jefes) pegando hashes inventados distintos.
    # Los cotejos siguientes igual quedan en el historial del archivo y en la cadena de custodia.
    existente = (
        db.query(Alerta)
        .filter(
            Alerta.archivo_id == archivo.id,
            Alerta.tipo == "cotejo_no_coincide",
            Alerta.atendida_en.is_(None),
        )
        .first()
    )
    if existente:
        return None
    origen_txt = f"{herramienta} ({referencia})" if referencia else herramienta
    alerta = Alerta(
        archivo_id=archivo.id,
        caso_id=archivo.caso_id,
        tipo="cotejo_no_coincide",
        ubicacion="original",
        hash_esperado=r["valor"],
        hash_encontrado=r["esperado"],
        detalle=(
            f"El {ETIQUETA_ALGORITMO[r['algoritmo']]} que reporta {origen_txt} no coincide con el de la "
            "evidencia custodiada. Puede ser otra extracción, un hash mal copiado o una evidencia distinta "
            "de la que procesó la herramienta."
        ),
        origen="cotejo",
    )
    db.add(alerta)
    db.flush()
    return alerta
