"""Sprint 5 (historia 19.1): roles y permisos centralizados.

Roles (modelo peruano, CPP 2004):
  - admin          → Jefe de laboratorio: todo.
  - perito         → Perito oficial: trabaja sus casos (crea, sube evidencia, verifica).
  - perito_parte   → Perito de parte (art. 177): ve y formula observaciones; no altera la evidencia.
  - fiscal         → Fiscal / auditor: solo lectura y reportes de todo el sistema.

Toda la lógica de "qué puede hacer cada rol" y "qué casos ve" vive aquí, así
las historias 19.2 y 19.3 (designación y subrogación) solo cambian este archivo.
"""
from fastapi import Depends, HTTPException
from sqlalchemy import false, true

from app.core.security import get_current_user
from app.models.caso import Caso
from app.models.usuario import RolEnum

ADMIN = RolEnum.admin
PERITO = RolEnum.perito
PERITO_PARTE = RolEnum.perito_parte
FISCAL = RolEnum.fiscal

# Acción → roles que la pueden realizar.
PERMISOS = {
    "crear_caso": {ADMIN, PERITO},
    "cambiar_estado_caso": {ADMIN, PERITO},
    "eliminar_caso": {ADMIN, PERITO},
    "papelera": {ADMIN, PERITO},
    "subir_evidencia": {ADMIN, PERITO},
    "editar_metadatos": {ADMIN, PERITO},
    "registrar_ficha": {ADMIN, PERITO},
    "verificar_integridad": {ADMIN, PERITO, PERITO_PARTE},
    "verificar_dispositivo": {ADMIN, PERITO},
    "descargar_original": {ADMIN, PERITO, FISCAL},
    "subir_observada": {ADMIN, PERITO, PERITO_PARTE},
    "atender_alertas": {ADMIN},
    "ver_dashboard": {ADMIN},
    "gestionar_usuarios": {ADMIN},
}

# Roles que ven TODOS los casos (en modo lectura en el caso del fiscal).
VEN_TODO = {ADMIN, FISCAL}

ETIQUETAS_ROL = {
    ADMIN: "Jefe de laboratorio",
    PERITO: "Perito oficial",
    PERITO_PARTE: "Perito de parte",
    FISCAL: "Fiscal / Auditor",
}


def puede(usuario, accion: str) -> bool:
    return usuario.rol in PERMISOS.get(accion, set())


def exigir(usuario, accion: str) -> None:
    """Lanza 403 si el usuario no tiene permiso para la acción."""
    if not puede(usuario, accion):
        raise HTTPException(
            status_code=403,
            detail=f"Tu rol ({ETIQUETAS_ROL.get(usuario.rol, usuario.rol)}) no tiene permiso para esta acción.",
        )


def requiere(accion: str):
    """Dependencia de FastAPI: `usuario = Depends(requiere("crear_caso"))`."""

    def _dependencia(usuario_actual=Depends(get_current_user)):
        exigir(usuario_actual, accion)
        return usuario_actual

    return _dependencia


def condicion_casos_visibles(usuario):
    """Condición SQL sobre `Caso` con los casos que el usuario puede ver.
    Historia 19.2 la amplía con los peritos designados al caso."""
    if usuario.rol in VEN_TODO:
        return true()
    if usuario.rol == PERITO:
        return Caso.usuario_id == usuario.id
    # Perito de parte: hasta que exista la designación (19.2) no ve casos.
    return false()


def puede_ver_caso(usuario, caso: Caso) -> bool:
    if usuario.rol in VEN_TODO:
        return True
    if usuario.rol == PERITO:
        return caso.usuario_id == usuario.id
    return False
