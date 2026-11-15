"""sprint 6: sello de tiempo RFC 3161 en reportes de auditoría y actas de juramento (H21)

Revision ID: d2f4a6c8e0b1
Revises: c8e1f3a5b7d9
Create Date: 2026-11-15 16:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "d2f4a6c8e0b1"
down_revision = "c8e1f3a5b7d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reportes_auditoria", sa.Column("tsa_token", sa.LargeBinary(), nullable=True))
    op.add_column("reportes_auditoria", sa.Column("tsa_fecha", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reportes_auditoria", sa.Column("tsa_serie", sa.String(), nullable=True))
    op.add_column("designaciones_pericia", sa.Column("juramento_tsa_token", sa.LargeBinary(), nullable=True))
    op.add_column("designaciones_pericia", sa.Column("juramento_tsa_fecha", sa.DateTime(timezone=True), nullable=True))
    op.add_column("designaciones_pericia", sa.Column("juramento_tsa_serie", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("designaciones_pericia", "juramento_tsa_serie")
    op.drop_column("designaciones_pericia", "juramento_tsa_fecha")
    op.drop_column("designaciones_pericia", "juramento_tsa_token")
    op.drop_column("reportes_auditoria", "tsa_serie")
    op.drop_column("reportes_auditoria", "tsa_fecha")
    op.drop_column("reportes_auditoria", "tsa_token")
