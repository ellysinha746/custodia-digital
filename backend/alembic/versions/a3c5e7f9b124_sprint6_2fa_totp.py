"""sprint 6: segundo factor TOTP (H24)

Revision ID: a3c5e7f9b124
Revises: f9b2d4a6c813
Create Date: 2026-11-13 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "a3c5e7f9b124"
down_revision = "f9b2d4a6c813"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("totp_secreto", sa.String(), nullable=True))
    op.add_column("usuarios", sa.Column("totp_activo", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("usuarios", sa.Column("totp_ultimo_paso", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("usuarios", "totp_ultimo_paso")
    op.drop_column("usuarios", "totp_activo")
    op.drop_column("usuarios", "totp_secreto")
