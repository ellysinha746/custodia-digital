"""sprint 7: análisis comparativo de firmas con OpenCV (H30)

Revision ID: b1d3f5a7c9e2
Revises: a8c0e2f4b6d7
Create Date: 2026-11-17 10:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b1d3f5a7c9e2"
down_revision = "a8c0e2f4b6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analisis_firmas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("caso_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("casos.id"), nullable=False, index=True),
        sa.Column("realizado_por_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("realizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dubitada_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("archivos.id"), nullable=False),
        sa.Column("entradas", postgresql.JSONB(), nullable=False),
        sa.Column("resultado", postgresql.JSONB(), nullable=False),
        sa.Column("hash_resultado", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("analisis_firmas")
