"""sprint 4: ficha del dispositivo en archivos

Revision ID: d3a7c9e15b42
Revises: b8e2d4f61a37
Create Date: 2026-10-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd3a7c9e15b42'
down_revision: Union[str, None] = 'b8e2d4f61a37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Sprint 4 (historia 13): IMEI, modelo, MAC y SO del dispositivo de origen
    op.add_column(
        'archivos',
        sa.Column('ficha_dispositivo', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'archivos',
        sa.Column('ficha_registrada_en', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('archivos', 'ficha_registrada_en')
    op.drop_column('archivos', 'ficha_dispositivo')