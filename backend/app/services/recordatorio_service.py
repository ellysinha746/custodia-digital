"""Sprint 6 (historia 26): recordatorio de plazos por vencer.

Revisa los tres plazos del procedimiento pericial y avisa por correo cuando faltan
RECORDATORIO_DIAS_ANTES días (o menos) para que venzan:

  aceptacion     → el perito oficial aún no acepta el cargo (art. 174)   → perito + fiscal
  emision        → la pericia sigue "designada" (falta emitir el informe) → perito + fiscal
  observaciones  → la parte está "en traslado" y aún puede observar      → perito de parte + fiscal

Cada plazo se recuerda UNA sola vez (tabla recordatorios_plazo). Si el plazo cambia,
por ejemplo tras una subrogación, el plazo nuevo genera su propio recordatorio.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Set
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.pericia import Pericia, RecordatorioPlazo
from app.services.correo_service import enviar_correo

LIMA = ZoneInfo("America/Lima")

TITULOS = {
    "aceptacion": "Aceptación del cargo de perito",
    "emision": "Emisión de la pericia",
    "observaciones": "Observaciones a la pericia (traslado)",
}

QUE_FALTA = {
    "aceptacion": "El perito oficial designado aún no acepta el cargo ni presta juramento (CPP art. 174).",
    "emision": "La pericia aún no ha sido emitida por el perito oficial.",
    "observaciones": "La parte investigada aún puede formular observaciones a través de su perito de parte.",
}


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _fecha(dt: datetime) -> str:
    return dt.astimezone(LIMA).strftime("%d/%m/%Y %H:%M") + " (hora de Lima)"


def _tiempo_restante(vence: datetime, ahora: datetime) -> str:
    horas = max(0, int((vence - ahora).total_seconds() // 3600))
    if horas < 24:
        return f"{horas} hora(s)"
    return f"{horas // 24} día(s) y {horas % 24} hora(s)"


def plazos_por_vencer(db, ahora: Optional[datetime] = None) -> List[dict]:
    """Lista de plazos que vencen dentro de la ventana de aviso (aún no vencidos)."""
    ahora = ahora or _ahora()
    limite = ahora + timedelta(days=settings.RECORDATORIO_DIAS_ANTES)
    resultado = []
    pericias = db.query(Pericia).filter(Pericia.estado.in_(["designada", "en_traslado", "observada"])).all()
    for p in pericias:
        fiscal = p.designada_por
        oficiales = [d for d in p.designaciones if d.activa and d.tipo == "oficial"]
        partes = [d for d in p.designaciones if d.activa and d.tipo == "parte"]

        if p.estado == "designada":
            for d in oficiales:
                if d.aceptacion == "pendiente" and d.aceptacion_vence_en and ahora < d.aceptacion_vence_en <= limite:
                    resultado.append({"pericia": p, "tipo": "aceptacion", "vence_en": d.aceptacion_vence_en,
                                      "usuarios": [d.usuario, fiscal]})
            vigentes = [d for d in oficiales if d.aceptacion != "inhibida"]
            if vigentes and p.fecha_limite and ahora < p.fecha_limite <= limite:
                resultado.append({"pericia": p, "tipo": "emision", "vence_en": p.fecha_limite,
                                  "usuarios": [d.usuario for d in vigentes] + [fiscal]})

        if p.estado in ("en_traslado", "observada") and p.traslado_vence_en and ahora < p.traslado_vence_en <= limite:
            resultado.append({"pericia": p, "tipo": "observaciones", "vence_en": p.traslado_vence_en,
                              "usuarios": [d.usuario for d in partes] + [fiscal]})

    # Un solo aviso por pericia, tipo y vencimiento (juntando a todos los destinatarios).
    unidos = {}
    for item in resultado:
        clave = (item["pericia"].id, item["tipo"], item["vence_en"])
        if clave in unidos:
            unidos[clave]["usuarios"] += item["usuarios"]
        else:
            unidos[clave] = item
    return list(unidos.values())


def _cuerpo(p: Pericia, tipo: str, vence: datetime, ahora: datetime) -> str:
    return (
        f"Recordatorio de plazo por vencer\n\n"
        f"Caso:        {p.caso.numero_caso}\n"
        f"Pericia:     {p.codigo} ({p.especialidad or 'sin especialidad'})\n"
        f"Plazo:       {TITULOS[tipo]}\n"
        f"Vence:       {_fecha(vence)}\n"
        f"Quedan:      {_tiempo_restante(vence, ahora)}\n\n"
        f"{QUE_FALTA[tipo]}\n\n"
        "Ingresa a CustodiaDigital para revisar la pericia."
    )


def enviar_recordatorios() -> int:
    """Envía los recordatorios pendientes. Devuelve cuántos se enviaron."""
    db = SessionLocal()
    enviados = 0
    try:
        ahora = _ahora()
        for item in plazos_por_vencer(db, ahora):
            p, tipo, vence = item["pericia"], item["tipo"], item["vence_en"]
            ya = (
                db.query(RecordatorioPlazo)
                .filter(RecordatorioPlazo.pericia_id == p.id, RecordatorioPlazo.tipo == tipo,
                        RecordatorioPlazo.vence_en == vence)
                .first()
            )
            if ya:
                continue
            correos: Set[str] = {u.email for u in item["usuarios"] if u is not None and u.activo}
            if not correos:
                continue
            # Primero se registra (la restricción única evita duplicados si dos procesos coinciden).
            registro = RecordatorioPlazo(pericia_id=p.id, tipo=tipo, vence_en=vence, destinatarios=sorted(correos))
            db.add(registro)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                continue
            asunto = f"[CustodiaDigital] Plazo por vencer: {TITULOS[tipo]} - {p.codigo}"
            enviar_correo(correos, asunto, _cuerpo(p, tipo, vence, ahora))
            enviados += 1
    finally:
        db.close()
    return enviados