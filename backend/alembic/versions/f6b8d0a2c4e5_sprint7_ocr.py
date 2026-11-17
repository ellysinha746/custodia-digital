"""sprint 7: OCR de documentos escaneados (H29)

Revision ID: f6b8d0a2c4e5
Revises: e4a6c8f0b2d3
Create Date: 2026-11-16 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "f6b8d0a2c4e5"
down_revision = "e4a6c8f0b2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("archivos", sa.Column("ocr_estado", sa.String(), nullable=True))
    op.add_column("archivos", sa.Column("ocr_texto", sa.Text(), nullable=True))
    op.add_column("archivos", sa.Column("ocr_confianza", sa.Float(), nullable=True))
    op.add_column("archivos", sa.Column("ocr_paginas", sa.Integer(), nullable=True))
    op.add_column("archivos", sa.Column("ocr_motor", sa.String(), nullable=True))
    op.add_column("archivos", sa.Column("ocr_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column("archivos", sa.Column("ocr_error", sa.String(), nullable=True))
    # Búsqueda de texto completo en español sobre el texto extraído.
    op.execute(
        "CREATE INDEX ix_archivos_ocr_fts ON archivos "
        "USING gin (to_tsvector('spanish', coalesce(ocr_texto, '')))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_archivos_ocr_fts")
    for columna in ("ocr_error", "ocr_en", "ocr_motor", "ocr_paginas", "ocr_confianza", "ocr_texto", "ocr_estado"):
        op.drop_column("archivos", columna)
