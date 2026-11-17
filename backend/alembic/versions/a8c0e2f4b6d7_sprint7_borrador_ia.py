"""sprint 7: borrador descriptivo asistido por IA (H34)

Revision ID: a8c0e2f4b6d7
Revises: f6b8d0a2c4e5
Create Date: 2026-11-16 16:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a8c0e2f4b6d7"
down_revision = "f6b8d0a2c4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "borradores_ia",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("caso_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("casos.id"), nullable=False, index=True),
        sa.Column("generado_por_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("generado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modelo_solicitado", sa.String(), nullable=False),
        sa.Column("modelo_respondio", sa.String(), nullable=True),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("texto_generado", sa.Text(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("documentos", postgresql.JSONB(), nullable=False),
        sa.Column("enviado", postgresql.JSONB(), nullable=False),
        sa.Column("tokens_entrada", sa.Integer(), nullable=True),
        sa.Column("tokens_salida", sa.Integer(), nullable=True),
        sa.Column("estado", sa.String(), nullable=False, server_default="borrador"),
        sa.Column("firmado_por_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("firmado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hash_texto", sa.String(), nullable=True),
        sa.Column("firma_hmac", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("borradores_ia")
