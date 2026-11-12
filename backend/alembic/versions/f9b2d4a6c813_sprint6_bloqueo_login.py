"""sprint 6: bloqueo temporal por intentos fallidos de login (H27)

Revision ID: f9b2d4a6c813
Revises: e7a1c3f5b209
Create Date: 2026-11-12 14:30:00
"""
from alembic import op
import sqlalchemy as sa

revision = "f9b2d4a6c813"
down_revision = "e7a1c3f5b209"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("intentos_fallidos", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("usuarios", sa.Column("bloqueado_hasta", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("usuarios", "bloqueado_hasta")
    op.drop_column("usuarios", "intentos_fallidos")