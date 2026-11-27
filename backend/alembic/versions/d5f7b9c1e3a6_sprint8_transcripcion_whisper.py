"""sprint 8: transcripción de audio y video con Whisper (H40)

Revision ID: d5f7b9c1e3a6
Revises: c3e5a7b9d1f4
Create Date: 2026-11-24 17:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d5f7b9c1e3a6"
down_revision = "c3e5a7b9d1f4"
branch_labels = None
depends_on = None

COLUMNAS = [
    ("transcripcion_estado", sa.String()),
    ("transcripcion_texto", sa.Text()),
    ("transcripcion_segmentos", postgresql.JSONB()),
    ("transcripcion_idioma", sa.String()),
    ("transcripcion_duracion", sa.Float()),
    ("transcripcion_motor", sa.String()),
    ("transcripcion_sha256", sa.String()),
    ("transcripcion_en", sa.DateTime(timezone=True)),
    ("transcripcion_error", sa.String()),
]


def upgrade() -> None:
    for nombre, tipo in COLUMNAS:
        op.add_column("archivos", sa.Column(nombre, tipo, nullable=True))
    # Búsqueda de texto completo en español dentro de lo que se dijo en los audios.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_archivos_transcripcion_fts ON archivos "
        "USING GIN (to_tsvector('spanish', coalesce(transcripcion_texto, '')))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_archivos_transcripcion_fts")
    for nombre, _ in reversed(COLUMNAS):
        op.drop_column("archivos", nombre)
