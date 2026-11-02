"""sprint 5: roles perito de parte y fiscal, usuarios activos

Revision ID: f2a6c8d0b913
Revises: e5b8f2a9c4d1
Create Date: 2026-11-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a6c8d0b913'
down_revision: Union[str, None] = 'e5b8f2a9c4d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Historia 19.1: nuevos roles del modelo peruano (CPP 2004)
    op.execute("ALTER TYPE rolenum ADD VALUE IF NOT EXISTS 'perito_parte'")
    op.execute("ALTER TYPE rolenum ADD VALUE IF NOT EXISTS 'fiscal'")

    # Historia 19.1: desactivar usuarios sin borrarlos (trazabilidad)
    op.add_column(
        'usuarios',
        sa.Column('activo', sa.Boolean(), server_default='true', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('usuarios', 'activo')
    # PostgreSQL no permite quitar valores de un ENUM; los roles nuevos se quedan.
