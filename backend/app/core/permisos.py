"""Sprint 5 (historia 19.1): roles y permisos centralizados.

Roles (modelo peruano, CPP 2004):
  - admin          → Jefe de laboratorio: todo.
  - perito         → Perito oficial: trabaja sus casos (crea, sube evidencia, verifica).
  - perito_parte   → Perito de parte (art. 177): ve y formula observaciones; no altera la evidencia.
  - fiscal         → Fiscal: ve todo, dirige el trámite pericial (designa, corre traslado,
                     pone en conocimiento, subroga, concluye). No sube ni altera evidencia.

Toda la lógica de "qué puede hacer cada rol" y "qué casos ve" vive aquí, así
las historias 19.2 y 19.3 (designación y subrogación) solo cambian este archivo.
"""
from fastapi import Depends, HTTPException
from sqlalchemy import and_, exists, false, or_, true

from app.core.security import get_current_user
from app.models.caso import Caso
from app.models.pericia import Pericia, DesignacionPericia
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
    # Sprint 5 (épica H19): el fiscal dirige el trámite pericial.
    "gestionar_pericias": {ADMIN, FISCAL},
    "ver_padron": {ADMIN, FISCAL, PERITO, PERITO_PARTE},
    "ver_perfil_ajeno": {ADMIN, FISCAL},
}

# Roles que ven TODOS los casos (en modo lectura en el caso del fiscal).
VEN_TODO = {ADMIN, FISCAL}

ETIQUETAS_ROL = {
    ADMIN: "Jefe de laboratorio",
    PERITO: "Perito oficial",
    PERITO_PARTE: "Perito de parte",
    FISCAL: "Fiscal",
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


def _designado_en_el_caso(usuario):
    """Existe una designación ACTIVA del usuario en alguna pericia del caso.
    Un perito subrogado deja de cumplir esta condición (pierde el acceso)."""
    return exists().where(
        and_(
            DesignacionPericia.pericia_id == Pericia.id,
            Pericia.caso_id == Caso.id,
            DesignacionPericia.usuario_id == usuario.id,
            DesignacionPericia.activa.is_(True),
        )
    )


def condicion_casos_visibles(usuario):
    """Condición SQL sobre `Caso` con los casos que el usuario puede ver.
    - Jefe de laboratorio y fiscal: todos.
    - Perito oficial: los que creó + aquellos donde está designado (19.3).
    - Perito de parte: solo aquellos donde está designado (19.7)."""
    if usuario.rol in VEN_TODO:
        return true()
    if usuario.rol == PERITO:
        return or_(Caso.usuario_id == usuario.id, _designado_en_el_caso(usuario))
    if usuario.rol == PERITO_PARTE:
        return _designado_en_el_caso(usuario)
    return false()


def puede_ver_caso(db, usuario, caso: Caso) -> bool:
    if usuario.rol in VEN_TODO:
        return True
    return (
        db.query(Caso.id).filter(Caso.id == caso.id, condicion_casos_visibles(usuario)).first()
        is not None
    )
