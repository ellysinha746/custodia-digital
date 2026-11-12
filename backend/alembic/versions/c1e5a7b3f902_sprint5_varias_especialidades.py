"""sprint 5: casos con varias especialidades, fiscal sin especialidad

Revision ID: c1e5a7b3f902
Revises: a9c3e7f1d204
Create Date: 2026-11-02 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c1e5a7b3f902'
down_revision: Union[str, None] = 'a9c3e7f1d204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # El fiscal y el jefe de laboratorio no tienen especialidad: solo los peritos.
    op.alter_column('usuarios', 'especialidad', nullable=True)
    op.execute("UPDATE usuarios SET especialidad = NULL WHERE rol::text IN ('fiscal', 'admin')")

    # Un caso puede abarcar varias especialidades (p. ej. telefonía + audio + video).
    op.add_column(
        'casos',
        sa.Column('especialidades', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    )
    # Los casos existentes conservan su especialidad como única de la lista.
    op.execute("UPDATE casos SET especialidades = jsonb_build_array(especialidad::text)")

    # Cada pericia indica en qué especialidad se hace.
    op.add_column('pericias', sa.Column('especialidad', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('pericias', 'especialidad')
    op.drop_column('casos', 'especialidades')
    op.execute("UPDATE usuarios SET especialidad = 'informatica' WHERE especialidad IS NULL")
    op.alter_column('usuarios', 'especialidad', nullable=False)
