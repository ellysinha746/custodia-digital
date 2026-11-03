"""Crea usuarios de DEMOSTRACIÓN: fiscales, peritos oficiales (2 por especialidad) y peritos de parte.

Las personas son FICTICIAS (nombres, registros y correos inventados); las instituciones son
las reales donde trabajan los peritos en el Perú. Los correos usan el dominio example.com, reservado para ejemplos,
así que ningún aviso del sistema le llega a una persona real.

Uso (con docker):
    docker compose exec api python -m app.scripts.crear_usuarios_demo

Se puede correr varias veces: si el correo ya existe, no lo vuelve a crear.
"""
from app.db.session import SessionLocal
from app.core.security import hash_password
from app.models.usuario import Usuario, RolEnum, EspecialidadEnum
import app.main  # noqa: F401  (carga todos los modelos)

CLAVE = "Demo2026!"

USUARIOS = [
    # nombre, correo, rol, especialidad, institución, registro, teléfono
    ("Fiscal Mariela Quispe Huamán", "fiscal.quispe@example.com", RolEnum.fiscal, None,
     "1ra Fiscalía Provincial Penal de Lima", None, None),
    ("Fiscal Ricardo Paredes León", "fiscal.paredes@example.com", RolEnum.fiscal, None,
     "Fiscalía Especializada en Ciberdelincuencia", None, None),

    ("Diego Ramírez Soto", "informatica1@example.com", RolEnum.perito, EspecialidadEnum.informatica,
     "DIRCRI PNP", "CIP 900101", "900 100 101"),
    ("Lucía Fernández Vega", "informatica2@example.com", RolEnum.perito, EspecialidadEnum.informatica,
     "Laboratorio de Criminalística del Ministerio Público", "CIP 900102", "900 100 102"),
    ("Carlos Mendoza Ruiz", "telefonia1@example.com", RolEnum.perito, EspecialidadEnum.telefonia,
     "DIRCRI PNP", "CIP 900201", "900 100 201"),
    ("Andrea Castillo Rojas", "telefonia2@example.com", RolEnum.perito, EspecialidadEnum.telefonia,
     "DIVINDAT PNP", "CIP 900202", "900 100 202"),
    ("Javier Torres Campos", "audio1@example.com", RolEnum.perito, EspecialidadEnum.audio,
     "DIRCRI PNP", "CIP 900301", "900 100 301"),
    ("Paola Vargas Medina", "audio2@example.com", RolEnum.perito, EspecialidadEnum.audio,
     "Instituto de Medicina Legal", "CIP 900302", "900 100 302"),
    ("Renzo Gutiérrez Silva", "video1@example.com", RolEnum.perito, EspecialidadEnum.video,
     "DIRCRI PNP", "CIP 900401", "900 100 401"),
    ("Sofía Herrera Díaz", "video2@example.com", RolEnum.perito, EspecialidadEnum.video,
     "Laboratorio de Criminalística del Ministerio Público", "CIP 900402", "900 100 402"),

    ("Martín Salazar Ortiz", "parte1@example.com", RolEnum.perito_parte, EspecialidadEnum.informatica,
     "Perito particular (REPEJ)", "REPEJ 0001", "900 200 001"),
    ("Valeria Chávez Núñez", "parte2@example.com", RolEnum.perito_parte, EspecialidadEnum.telefonia,
     "Perito particular (REPEJ)", "REPEJ 0002", "900 200 002"),
    ("Hugo Palacios Reyes", "parte3@example.com", RolEnum.perito_parte, EspecialidadEnum.audio,
     "Perito particular (REPEJ)", "REPEJ 0003", "900 200 003"),
]


def main() -> None:
    db = SessionLocal()
    creados, existentes = [], []
    try:
        for nombre, email, rol, esp, inst, reg, tel in USUARIOS:
            if db.query(Usuario).filter(Usuario.email == email).first():
                existentes.append(email)
                continue
            db.add(Usuario(
                nombre=nombre, email=email, password_hash=hash_password(CLAVE), rol=rol, especialidad=esp,
                institucion=inst, registro_profesional=reg, telefono=tel, activo=True,
            ))
            creados.append((rol.value, esp.value if esp else "—", nombre, email))
        db.commit()
    finally:
        db.close()

    print(f"\nCreados: {len(creados)}  ·  Ya existían: {len(existentes)}")
    for rol, esp, nombre, email in creados:
        print(f"  {rol:<13} {esp:<12} {nombre:<32} {email}")
    print(f"\nContraseña de todos: {CLAVE}\n")


if __name__ == "__main__":
    main()
