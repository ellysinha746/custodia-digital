"""sprint 6: solicitudes de cuenta (H25), metadatos técnicos (H20) y recordatorios de plazo (H26)

Revision ID: e7a1c3f5b209
Revises: d4f8b2c6e1a7
Create Date: 2026-11-10 21:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e7a1c3f5b209"
down_revision = "d4f8b2c6e1a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # H25: una cuenta pedida desde "Solicitar acceso" queda pendiente hasta que el jefe la aprueba.
    op.add_column("usuarios", sa.Column("estado_solicitud", sa.String(), nullable=True))

    # H20: metadatos extraídos automáticamente (EXIF, ffprobe, PDF, tipo real del archivo).
    op.add_column("archivos", sa.Column("metadatos_tecnicos", postgresql.JSONB(), nullable=True))

    # H26: un recordatorio por pericia, tipo de plazo y fecha de vencimiento (evita duplicados).
    op.create_table(
        "recordatorios_plazo",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pericia_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pericias.id"), nullable=False, index=True),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("vence_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("destinatarios", postgresql.JSONB(), nullable=True),
        sa.Column("enviado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("pericia_id", "tipo", "vence_en", name="uq_recordatorio_plazo"),
    )


def downgrade() -> None:
    op.drop_table("recordatorios_plazo")
    op.drop_column("archivos", "metadatos_tecnicos")
    op.drop_column("usuarios", "estado_solicitud")