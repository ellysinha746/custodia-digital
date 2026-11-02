"""sprint 4: versiones observadas, reportes de auditoria y fecha de cierre

Revision ID: e5b8f2a9c4d1
Revises: d3a7c9e15b42
Create Date: 2026-11-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e5b8f2a9c4d1'
down_revision: Union[str, None] = 'd3a7c9e15b42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Historia 14: versiones con observaciones de otro perito
    op.create_table(
        'versiones_observadas',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('archivo_id', sa.UUID(), nullable=False),
        sa.Column('nombre', sa.String(), nullable=False),
        sa.Column('ruta', sa.String(), nullable=False),
        sa.Column('hash_sha256', sa.String(), nullable=False),
        sa.Column('observaciones', sa.Text(), nullable=False),
        sa.Column('subido_por_id', sa.UUID(), nullable=False),
        sa.Column('subido_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['archivo_id'], ['archivos.id']),
        sa.ForeignKeyConstraint(['subido_por_id'], ['usuarios.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_versiones_observadas_archivo_id'), 'versiones_observadas', ['archivo_id'], unique=False)

    # Historia 16: reportes de auditoría exportados con sello de tiempo
    op.create_table(
        'reportes_auditoria',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('folio', sa.String(), nullable=False),
        sa.Column('formato', sa.String(), nullable=False),
        sa.Column('filtros', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('total_eventos', sa.Integer(), nullable=False),
        sa.Column('hash_contenido', sa.String(), nullable=False),
        sa.Column('hash_archivo', sa.String(), nullable=False),
        sa.Column('firma', sa.String(), nullable=False),
        sa.Column('generado_en', sa.DateTime(timezone=True), nullable=False),
        sa.Column('generado_por_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['generado_por_id'], ['usuarios.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('folio'),
    )
    op.create_index(op.f('ix_reportes_auditoria_hash_archivo'), 'reportes_auditoria', ['hash_archivo'], unique=False)

    # Historia 18: fecha de cierre del caso, para el tiempo promedio de cierre
    op.add_column('casos', sa.Column('cerrado_en', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('casos', 'cerrado_en')
    op.drop_index(op.f('ix_reportes_auditoria_hash_archivo'), table_name='reportes_auditoria')
    op.drop_table('reportes_auditoria')
    op.drop_index(op.f('ix_versiones_observadas_archivo_id'), table_name='versiones_observadas')
    op.drop_table('versiones_observadas')