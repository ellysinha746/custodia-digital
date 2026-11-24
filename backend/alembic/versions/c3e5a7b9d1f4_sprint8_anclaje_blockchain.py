"""sprint 8: anclaje del historial de custodia en Bitcoin con OpenTimestamps (H39)

Revision ID: c3e5a7b9d1f4
Revises: b1d3f5a7c9e2
Create Date: 2026-11-24 16:30:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c3e5a7b9d1f4"
down_revision = "b1d3f5a7c9e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "anclajes_blockchain",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("creado_por_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("hasta", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_registros", sa.Integer(), nullable=False),
        sa.Column("huella", sa.String(64), nullable=False),
        sa.Column("prueba_ots", sa.LargeBinary(), nullable=False),
        sa.Column("calendarios", postgresql.JSONB(), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False, server_default="pendiente"),
        sa.Column("bloque_bitcoin", sa.Integer(), nullable=True),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_anclajes_blockchain_hasta", "anclajes_blockchain", ["hasta"])


def downgrade() -> None:
    op.drop_index("ix_anclajes_blockchain_hasta", table_name="anclajes_blockchain")
    op.drop_table("anclajes_blockchain")
