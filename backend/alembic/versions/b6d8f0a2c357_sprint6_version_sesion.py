"""sprint 6: versión de sesión para cerrar sesiones al reiniciar el 2FA (H24)

Revision ID: b6d8f0a2c357
Revises: a3c5e7f9b124
Create Date: 2026-11-13 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "b6d8f0a2c357"
down_revision = "a3c5e7f9b124"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("sesion_version", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("usuarios", "sesion_version")
