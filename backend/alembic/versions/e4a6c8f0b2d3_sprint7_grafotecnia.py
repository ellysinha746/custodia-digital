"""sprint 7: especialidad grafotecnia y documentos dubitados / indubitados (H28)

Revision ID: e4a6c8f0b2d3
Revises: d2f4a6c8e0b1
Create Date: 2026-11-16 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "e4a6c8f0b2d3"
down_revision = "d2f4a6c8e0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # En Postgres un valor nuevo de un enum no se puede agregar (ni usar) dentro de la
    # transacción de la migración: va en un bloque con autocommit.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE especialidadenum ADD VALUE IF NOT EXISTS 'grafotecnia'")
    op.add_column("archivos", sa.Column("rol_grafotecnico", sa.String(), nullable=True))
    op.create_check_constraint(
        "ck_archivos_rol_grafotecnico", "archivos", "rol_grafotecnico IN ('dubitado', 'indubitado')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_archivos_rol_grafotecnico", "archivos", type_="check")
    op.drop_column("archivos", "rol_grafotecnico")
    # Postgres no permite quitar un valor de un enum: 'grafotecnia' queda en especialidadenum.
