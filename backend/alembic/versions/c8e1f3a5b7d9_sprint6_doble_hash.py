"""sprint 6: doble hash (SHA-1 y MD5) y cotejos con herramientas forenses (H23)

Revision ID: c8e1f3a5b7d9
Revises: b6d8f0a2c357
Create Date: 2026-11-15 10:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c8e1f3a5b7d9"
down_revision = "b6d8f0a2c357"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("archivos", sa.Column("hash_sha1", sa.String(), nullable=True))
    op.add_column("archivos", sa.Column("hash_md5", sa.String(), nullable=True))
    op.add_column("archivos", sa.Column("cotejos", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("archivos", "cotejos")
    op.drop_column("archivos", "hash_md5")
    op.drop_column("archivos", "hash_sha1")
