import json
import re
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.api.archivos import _obtener_archivo, _obtener_caso_editable
from app.models.alerta import Alerta
from app.models.log_custodia import LogCustodia, AccionEnum
from app.schemas.archivo import ArchivoOut
from app.schemas.ficha import FichaDispositivoIn, VerificacionDispositivoOut, CampoComparado
from app.services.ficha_service import (
    CAMPOS_FICHA,
    normalizar_ficha,
    comparar_fichas,
    ficha_a_csv,
)
from app.services.integridad_service import notificar_alerta

router = APIRouter(tags=["ficha del dispositivo"])


@router.put("/archivos/{archivo_id}/ficha", response_model=ArchivoOut)
def registrar_ficha(
    archivo_id: UUID,
    payload: FichaDispositivoIn,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Registra la ficha de un archivo que se subió sin ella.
    Una vez registrada NO se puede cambiar: es la referencia contra la que
    se compara después para detectar si el dispositivo fue sustituido."""
    archivo = _obtener_archivo(db, archivo_id, usuario_actual)
    _obtener_caso_editable(db, archivo.caso_id, usuario_actual)
    if archivo.ficha_dispositivo:
        raise HTTPException(
            status_code=409,
            detail="La ficha del dispositivo ya está registrada y no se puede modificar.",
        )

    ficha = normalizar_ficha(payload.model_dump())
    if not ficha:
        raise HTTPException(status_code=400, detail="Ingresa al menos un dato del dispositivo.")

    archivo.ficha_dispositivo = ficha
    archivo.ficha_registrada_en = datetime.now(timezone.utc)
    db.add(
        LogCustodia(
            archivo_id=archivo.id,
            usuario_id=usuario_actual.id,
            accion=AccionEnum.subida,
            resultado="ficha_dispositivo",
        )
    )
    db.commit()
    db.refresh(archivo)
    return archivo


@router.post("/archivos/{archivo_id}/verificar-dispositivo", response_model=VerificacionDispositivoOut)
def verificar_dispositivo(
    archivo_id: UUID,
    payload: FichaDispositivoIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Historia 13: compara los datos que el perito lee hoy del dispositivo
    con la ficha registrada en la subida. Si algún campo no coincide se
    genera una alerta (y su correo, historia 15)."""
    archivo = _obtener_archivo(db, archivo_id, usuario_actual)
    if not archivo.ficha_dispositivo:
        raise HTTPException(
            status_code=409,
            detail="Este archivo no tiene ficha del dispositivo registrada.",
        )

    actual = normalizar_ficha(payload.model_dump())
    campos = comparar_fichas(archivo.ficha_dispositivo, actual)
    comparados = [c for c in campos if c["estado"] in ("coincide", "distinto")]
    if not comparados:
        raise HTTPException(
            status_code=400,
            detail="Ingresa al menos un dato que también esté en la ficha registrada.",
        )

    distintos = [c for c in comparados if c["estado"] == "distinto"]
    resultado = "dispositivo_distinto" if distintos else "dispositivo_coincide"

    log = LogCustodia(
        archivo_id=archivo.id,
        usuario_id=usuario_actual.id,
        accion=AccionEnum.verificacion,
        resultado=resultado,
    )
    db.add(log)

    alerta = None
    if distintos:
        detalle = "Posible sustitución del dispositivo de origen. " + "; ".join(
            f"{c['etiqueta']}: registrado {c['registrado']}, verificado {c['actual']}" for c in distintos
        ) + "."
        # No duplicar si ya hay una alerta pendiente por la misma diferencia.
        existente = (
            db.query(Alerta)
            .filter(
                Alerta.archivo_id == archivo.id,
                Alerta.tipo == "dispositivo_sustituido",
                Alerta.atendida_en.is_(None),
                Alerta.detalle == detalle,
            )
            .first()
        )
        if not existente:
            alerta = Alerta(
                archivo_id=archivo.id,
                caso_id=archivo.caso_id,
                tipo="dispositivo_sustituido",
                ubicacion="dispositivo",
                detalle=detalle,
                origen="verificacion_manual",
            )
            db.add(alerta)

    db.commit()
    db.refresh(log)
    if alerta:
        db.refresh(alerta)
        background_tasks.add_task(notificar_alerta, alerta.id)

    return VerificacionDispositivoOut(
        archivo_id=archivo.id,
        resultado=resultado,
        campos=[CampoComparado(**c) for c in campos],
        alerta_id=alerta.id if alerta else None,
        verificado_en=log.fecha,
    )


def _nombre_seguro(texto: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", texto).strip("_") or "archivo"


@router.get("/archivos/{archivo_id}/ficha/exportar")
def exportar_ficha(
    archivo_id: UUID,
    formato: Literal["json", "csv"] = "json",
    db: Session = Depends(get_db),
    usuario_actual=Depends(get_current_user),
):
    """Historia 17: ficha del dispositivo como anexo técnico (JSON o CSV)."""
    archivo = _obtener_archivo(db, archivo_id, usuario_actual)
    if not archivo.ficha_dispositivo:
        raise HTTPException(
            status_code=409,
            detail="Este archivo no tiene ficha del dispositivo registrada.",
        )

    caso = archivo.caso
    ultima = (
        db.query(LogCustodia)
        .filter(
            LogCustodia.archivo_id == archivo.id,
            LogCustodia.resultado.in_(["dispositivo_coincide", "dispositivo_distinto"]),
        )
        .order_by(LogCustodia.fecha.desc())
        .first()
    )
    ahora = datetime.now(timezone.utc)
    ficha = archivo.ficha_dispositivo

    documento = {
        "tipo_documento": "Ficha de metadatos del dispositivo de origen",
        "caso": {"numero": caso.numero_caso, "especialidad": caso.especialidad.value},
        "archivo": {
            "id": str(archivo.id),
            "nombre": archivo.nombre_original,
            "hash_sha256_original": archivo.hash_original,
            "subido_en": archivo.subido_en.isoformat() if archivo.subido_en else None,
        },
        "dispositivo": {clave: ficha.get(clave) for clave in CAMPOS_FICHA},
        "ficha_registrada_en": archivo.ficha_registrada_en.isoformat() if archivo.ficha_registrada_en else None,
        "ultima_verificacion_dispositivo": (
            {
                "fecha": ultima.fecha.isoformat(),
                "resultado": ultima.resultado,
                "verificado_por": ultima.usuario.nombre,
            }
            if ultima
            else None
        ),
        "exportado_en": ahora.isoformat(),
        "exportado_por": usuario_actual.nombre,
    }

    db.add(
        LogCustodia(
            archivo_id=archivo.id,
            usuario_id=usuario_actual.id,
            accion=AccionEnum.descarga,
            resultado=f"ficha_{formato}",
        )
    )
    db.commit()

    base = f"ficha_{_nombre_seguro(caso.numero_caso)}_{_nombre_seguro(archivo.nombre_original)}"
    if formato == "json":
        contenido = json.dumps(documento, ensure_ascii=False, indent=2).encode("utf-8")
        tipo = "application/json"
    else:
        filas = [
            ("tipo_documento", documento["tipo_documento"]),
            ("caso_numero", caso.numero_caso),
            ("caso_especialidad", caso.especialidad.value),
            ("archivo_id", str(archivo.id)),
            ("archivo_nombre", archivo.nombre_original),
            ("hash_sha256_original", archivo.hash_original),
            ("archivo_subido_en", documento["archivo"]["subido_en"]),
        ]
        filas += [(clave, ficha.get(clave)) for clave in CAMPOS_FICHA]
        filas += [("ficha_registrada_en", documento["ficha_registrada_en"])]
        if ultima:
            filas += [
                ("ultima_verificacion_fecha", documento["ultima_verificacion_dispositivo"]["fecha"]),
                ("ultima_verificacion_resultado", ultima.resultado),
                ("ultima_verificacion_por", ultima.usuario.nombre),
            ]
        filas += [("exportado_en", documento["exportado_en"]), ("exportado_por", usuario_actual.nombre)]
        contenido = ficha_a_csv(filas)
        tipo = "text/csv; charset=utf-8"

    return Response(
        content=contenido,
        media_type=tipo,
        headers={"Content-Disposition": f'attachment; filename="{base}.{formato}"'},
    )