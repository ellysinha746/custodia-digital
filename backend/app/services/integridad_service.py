import os
from datetime import timezone
from typing import Optional, Tuple, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.core.config import settings
from app.models.archivo import Archivo, EstadoProcesamientoEnum
from app.models.caso import Caso
from app.models.usuario import Usuario, RolEnum
from app.models.alerta import Alerta
from app.services.hashing_service import calcular_sha256
from app.services.correo_service import enviar_correo


def _hash_o_none(ruta: str) -> Optional[str]:
    return calcular_sha256(ruta) if os.path.exists(ruta) else None


def revisar_archivo(
    db: Session, archivo: Archivo, origen: str
) -> Tuple[str, Optional[str], Optional[str], Optional[Alerta]]:
    """Recalcula el hash del ORIGINAL y de la COPIA y los compara con el hash
    registrado en la subida.

    El sistema no tiene ninguna acción que modifique legítimamente esos dos
    archivos (las versiones observadas se guardan aparte), así que cualquier
    diferencia es un cambio SIN registro de custodia que lo respalde → alerta.

    No hace commit: lo hace quien llama.
    Devuelve (resultado, hash_original_hoy, hash_copia_hoy, alerta_nueva)."""
    esperado = archivo.hash_original
    h_original = _hash_o_none(archivo.ruta_original)
    h_copia = _hash_o_none(archivo.ruta_copia_trabajo)

    alterados = []
    if h_original != esperado:
        alterados.append("original")
    if h_copia != esperado:
        alterados.append("copia")

    if not alterados:
        return "integro", h_original, h_copia, None

    ubicacion = "ambos" if len(alterados) == 2 else alterados[0]
    hash_encontrado = h_original if "original" in alterados else h_copia

    partes = []
    for cual, h in (("original", h_original), ("copia", h_copia)):
        if cual in alterados:
            nombre = "El archivo original" if cual == "original" else "La copia de trabajo"
            partes.append(f"{nombre} ya no existe en el almacenamiento." if h is None
                          else f"{nombre} cambió de hash.")
    detalle = " ".join(partes) + " No hay un registro de custodia que respalde el cambio."

    # No duplicar: si ya hay una alerta pendiente por el mismo cambio, se reutiliza.
    existente = (
        db.query(Alerta)
        .filter(
            Alerta.archivo_id == archivo.id,
            Alerta.atendida_en.is_(None),
            Alerta.ubicacion == ubicacion,
            Alerta.hash_encontrado == hash_encontrado,
        )
        .first()
    )
    if existente:
        return "alterado", h_original, h_copia, None

    alerta = Alerta(
        archivo_id=archivo.id,
        caso_id=archivo.caso_id,
        tipo="hash_sin_respaldo",
        ubicacion=ubicacion,
        hash_esperado=esperado,
        hash_encontrado=hash_encontrado,
        detalle=detalle,
        origen=origen,
    )
    db.add(alerta)
    db.flush()  # para tener alerta.id antes del commit
    return "alterado", h_original, h_copia, alerta


def escanear_todos() -> Tuple[int, List[UUID]]:
    """Revisa todos los archivos listos de casos no eliminados.
    Devuelve (archivos_revisados, ids_de_alertas_nuevas)."""
    db = SessionLocal()
    revisados = 0
    nuevas: List[UUID] = []
    try:
        archivos = (
            db.query(Archivo)
            .join(Caso, Archivo.caso_id == Caso.id)
            .filter(
                Caso.eliminado_en.is_(None),
                Archivo.estado_procesamiento == EstadoProcesamientoEnum.listo,
                Archivo.hash_original.isnot(None),
            )
            .all()
        )
        for archivo in archivos:
            _, _, h_copia, alerta = revisar_archivo(db, archivo, origen="escaneo_automatico")
            archivo.hash_actual = h_copia
            revisados += 1
            if alerta:
                nuevas.append(alerta.id)
        db.commit()
    finally:
        db.close()
    return revisados, nuevas


def notificar_alerta(alerta_id: UUID) -> None:
    """Historias 12 y 15: correo a los admins y al perito dueño del caso.
    Abre su propia sesión porque corre en segundo plano."""
    db = SessionLocal()
    try:
        alerta = db.query(Alerta).filter(Alerta.id == alerta_id).first()
        if not alerta or alerta.correo_enviado:
            return

        caso = alerta.caso
        archivo = alerta.archivo
        destinatarios = {u.email for u in db.query(Usuario).filter(Usuario.rol == RolEnum.admin).all()}
        destinatarios.add(caso.usuario.email)
        if settings.ALERTAS_EMAIL_ADMIN:
            destinatarios.add(settings.ALERTAS_EMAIL_ADMIN)

        fecha = alerta.creada_en.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M:%S UTC")
        origen = "verificación manual" if alerta.origen == "verificacion_manual" else "escaneo automático"
        asunto = f"[CustodiaDigital] Alerta de integridad - Caso {caso.numero_caso}"
        if alerta.tipo == "dispositivo_sustituido":
            # Sprint 4 (historia 13): la ficha del dispositivo no coincide.
            intro = "La ficha del dispositivo de origen no coincide con la registrada en la subida.\n\n"
            lineas_hash = ""
        else:
            intro = "Se detectó un cambio en una evidencia sin un registro de custodia que lo respalde.\n\n"
            lineas_hash = (
                f"Hash esperado:   {alerta.hash_esperado}\n"
                f"Hash encontrado: {alerta.hash_encontrado or '(archivo inexistente)'}\n"
            )
        cuerpo = (
            intro
            + f"Caso:            {caso.numero_caso}\n"
            f"Archivo:         {archivo.nombre_original}\n"
            f"Afectado:        {alerta.ubicacion}\n"
            + lineas_hash
            + f"Detectado por:   {origen}\n"
            f"Fecha:           {fecha}\n\n"
            f"{alerta.detalle}\n\n"
            "Revisa la sección Alertas de CustodiaDigital para investigar y marcarla como atendida."
        )

        if enviar_correo(destinatarios, asunto, cuerpo):
            alerta.correo_enviado = True
            db.commit()
    finally:
        db.close()