"""sprint 4: tabla de alertas de integridad

Revision ID: b8e2d4f61a37
Revises: 7f3b9a1c2d4e
Create Date: 2026-10-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8e2d4f61a37'
down_revision: Union[str, None] = '7f3b9a1c2d4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'alertas',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('archivo_id', sa.UUID(), nullable=False),
        sa.Column('caso_id', sa.UUID(), nullable=False),
        sa.Column('tipo', sa.String(), nullable=False),
        sa.Column('ubicacion', sa.String(), nullable=False),
        sa.Column('hash_esperado', sa.String(), nullable=True),
        sa.Column('hash_encontrado', sa.String(), nullable=True),
        sa.Column('detalle', sa.String(), nullable=False),
        sa.Column('origen', sa.String(), nullable=False),
        sa.Column('correo_enviado', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('creada_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('atendida_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('atendida_por_id', sa.UUID(), nullable=True),
        sa.Column('nota_atencion', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['archivo_id'], ['archivos.id']),
        sa.ForeignKeyConstraint(['caso_id'], ['casos.id']),
        sa.ForeignKeyConstraint(['atendida_por_id'], ['usuarios.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_alertas_archivo_id'), 'alertas', ['archivo_id'], unique=False)
    op.create_index(op.f('ix_alertas_caso_id'), 'alertas', ['caso_id'], unique=False)
    op.create_index(op.f('ix_alertas_creada_en'), 'alertas', ['creada_en'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_alertas_creada_en'), table_name='alertas')
    op.drop_index(op.f('ix_alertas_caso_id'), table_name='alertas')
    op.drop_index(op.f('ix_alertas_archivo_id'), table_name='alertas')
    op.drop_table('alertas')