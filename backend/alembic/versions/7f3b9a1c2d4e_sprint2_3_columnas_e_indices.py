"""sprint 2 y 3: estado de procesamiento, papelera, indices

Revision ID: 7f3b9a1c2d4e
Revises: ca895226df84
Create Date: 2026-10-22 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f3b9a1c2d4e'
down_revision: Union[str, None] = 'ca895226df84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Sprint 2: estado de procesamiento para subidas pesadas en segundo plano
    estado_procesamiento_enum = sa.Enum(
        'pendiente', 'procesando', 'listo', name='estadoprocesamientoenum'
    )
    estado_procesamiento_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'archivos',
        sa.Column(
            'estado_procesamiento',
            estado_procesamiento_enum,
            nullable=False,
            server_default='listo',
        ),
    )
    # El hash se calcula en segundo plano para archivos pesados: queda nulo
    # hasta que el proceso en background lo completa.
    op.alter_column('archivos', 'hash_original', existing_type=sa.String(), nullable=True)

    # Sprint 2: indexar estado del caso (consultas por estado, evita full scan)
    op.create_index(op.f('ix_casos_estado'), 'casos', ['estado'], unique=False)

    # Sprint 2: buscador por nombre de archivo
    op.create_index(
        op.f('ix_archivos_nombre_original'), 'archivos', ['nombre_original'], unique=False
    )

    # Sprint 3: papelera de 30 dias (soft delete)
    op.add_column('casos', sa.Column('eliminado_en', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_casos_eliminado_en'), 'casos', ['eliminado_en'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_casos_eliminado_en'), table_name='casos')
    op.drop_column('casos', 'eliminado_en')
    op.drop_index(op.f('ix_archivos_nombre_original'), table_name='archivos')
    op.drop_index(op.f('ix_casos_estado'), table_name='casos')
    op.alter_column('archivos', 'hash_original', existing_type=sa.String(), nullable=False)
    op.drop_column('archivos', 'estado_procesamiento')
    sa.Enum(name='estadoprocesamientoenum').drop(op.get_bind(), checkfirst=True)
