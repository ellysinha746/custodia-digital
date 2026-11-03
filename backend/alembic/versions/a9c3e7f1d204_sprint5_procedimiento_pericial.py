"""sprint 5: padron de peritos y procedimiento pericial

Revision ID: a9c3e7f1d204
Revises: f2a6c8d0b913
Create Date: 2026-11-02 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a9c3e7f1d204'
down_revision: Union[str, None] = 'f2a6c8d0b913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Historia 19.2: ficha profesional del perito (padrón)
    op.add_column('usuarios', sa.Column('institucion', sa.String(), nullable=True))
    op.add_column('usuarios', sa.Column('registro_profesional', sa.String(), nullable=True))
    op.add_column('usuarios', sa.Column('telefono', sa.String(), nullable=True))

    # Historias 19.3 a 19.6: la pericia y su trámite
    op.create_table(
        'pericias',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('caso_id', sa.UUID(), nullable=False),
        sa.Column('codigo', sa.String(), nullable=False),
        sa.Column('estado', sa.String(), nullable=False),
        sa.Column('disposicion_fiscal', sa.String(), nullable=False),
        sa.Column('objetivos', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('plazo_dias', sa.Integer(), nullable=False),
        sa.Column('fecha_limite', sa.DateTime(timezone=True), nullable=False),
        sa.Column('designada_por_id', sa.UUID(), nullable=False),
        sa.Column('designada_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('informe_nombre', sa.String(), nullable=True),
        sa.Column('informe_ruta', sa.String(), nullable=True),
        sa.Column('informe_hash', sa.String(), nullable=True),
        sa.Column('emitida_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('traslado_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('traslado_plazo_dias', sa.Integer(), nullable=True),
        sa.Column('traslado_vence_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('conocimiento_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('absuelta_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('concluida_en', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['caso_id'], ['casos.id']),
        sa.ForeignKeyConstraint(['designada_por_id'], ['usuarios.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('codigo'),
    )
    op.create_index(op.f('ix_pericias_caso_id'), 'pericias', ['caso_id'], unique=False)
    op.create_index(op.f('ix_pericias_estado'), 'pericias', ['estado'], unique=False)

    # Historias 19.3, 19.7 y 19.8: designaciones (oficial / parte) y subrogación
    op.create_table(
        'designaciones_pericia',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('pericia_id', sa.UUID(), nullable=False),
        sa.Column('usuario_id', sa.UUID(), nullable=False),
        sa.Column('tipo', sa.String(), nullable=False),
        sa.Column('documento', sa.String(), nullable=True),
        sa.Column('designado_por_id', sa.UUID(), nullable=False),
        sa.Column('designado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('activa', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('subrogado_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('motivo_subrogacion', sa.String(), nullable=True),
        sa.Column('documento_subrogacion', sa.String(), nullable=True),
        sa.Column('subrogado_por_id', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['pericia_id'], ['pericias.id']),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id']),
        sa.ForeignKeyConstraint(['designado_por_id'], ['usuarios.id']),
        sa.ForeignKeyConstraint(['subrogado_por_id'], ['usuarios.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_designaciones_pericia_pericia_id'), 'designaciones_pericia', ['pericia_id'], unique=False)
    op.create_index(op.f('ix_designaciones_pericia_usuario_id'), 'designaciones_pericia', ['usuario_id'], unique=False)

    # Historias 19.5 y 19.6: observaciones de la parte y su absolución
    op.create_table(
        'observaciones_pericia',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('pericia_id', sa.UUID(), nullable=False),
        sa.Column('autor_id', sa.UUID(), nullable=False),
        sa.Column('texto', sa.Text(), nullable=False),
        sa.Column('anexo_nombre', sa.String(), nullable=True),
        sa.Column('anexo_ruta', sa.String(), nullable=True),
        sa.Column('anexo_hash', sa.String(), nullable=True),
        sa.Column('creada_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('respuesta', sa.Text(), nullable=True),
        sa.Column('respondida_por_id', sa.UUID(), nullable=True),
        sa.Column('respondida_en', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['pericia_id'], ['pericias.id']),
        sa.ForeignKeyConstraint(['autor_id'], ['usuarios.id']),
        sa.ForeignKeyConstraint(['respondida_por_id'], ['usuarios.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_observaciones_pericia_pericia_id'), 'observaciones_pericia', ['pericia_id'], unique=False)

    # Línea de tiempo de la pericia
    op.create_table(
        'eventos_pericia',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('pericia_id', sa.UUID(), nullable=False),
        sa.Column('usuario_id', sa.UUID(), nullable=False),
        sa.Column('tipo', sa.String(), nullable=False),
        sa.Column('detalle', sa.String(), nullable=True),
        sa.Column('fecha', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['pericia_id'], ['pericias.id']),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_eventos_pericia_pericia_id'), 'eventos_pericia', ['pericia_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_eventos_pericia_pericia_id'), table_name='eventos_pericia')
    op.drop_table('eventos_pericia')
    op.drop_index(op.f('ix_observaciones_pericia_pericia_id'), table_name='observaciones_pericia')
    op.drop_table('observaciones_pericia')
    op.drop_index(op.f('ix_designaciones_pericia_usuario_id'), table_name='designaciones_pericia')
    op.drop_index(op.f('ix_designaciones_pericia_pericia_id'), table_name='designaciones_pericia')
    op.drop_table('designaciones_pericia')
    op.drop_index(op.f('ix_pericias_estado'), table_name='pericias')
    op.drop_index(op.f('ix_pericias_caso_id'), table_name='pericias')
    op.drop_table('pericias')
    op.drop_column('usuarios', 'telefono')
    op.drop_column('usuarios', 'registro_profesional')
    op.drop_column('usuarios', 'institucion')
