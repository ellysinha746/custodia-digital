"""sprint 5: aceptación del cargo, inhibición y juramento del perito oficial

Revision ID: d4f8b2c6e1a7
Revises: c1e5a7b3f902
Create Date: 2026-11-02 21:30:00
"""
from alembic import op
import sqlalchemy as sa

revision = "d4f8b2c6e1a7"
down_revision = "c1e5a7b3f902"
branch_labels = None
depends_on = None

COLUMNAS = [
    ("aceptacion", sa.String()),
    ("aceptacion_vence_en", sa.DateTime(timezone=True)),
    ("aceptada_en", sa.DateTime(timezone=True)),
    ("inhibicion_motivo", sa.String()),
    ("inhibicion_detalle", sa.Text()),
    ("juramento_forma", sa.String()),
    ("juramento_texto", sa.Text()),
    ("juramento_en", sa.DateTime(timezone=True)),
    ("juramento_hash", sa.String()),
    ("juramento_firma", sa.String()),
]


def upgrade() -> None:
    for nombre, tipo in COLUMNAS:
        op.add_column("designaciones_pericia", sa.Column(nombre, tipo, nullable=True))

    # Pericias que ya avanzaron: el perito oficial se da por aceptado (registro histórico, sin acta).
    op.execute(
        """
        UPDATE designaciones_pericia d
           SET aceptacion = 'aceptada', aceptada_en = d.designado_en,
               juramento_forma = 'historico', juramento_en = d.designado_en,
               juramento_texto = 'Registro anterior a la juramentación en línea.'
          FROM pericias p
         WHERE p.id = d.pericia_id AND d.tipo = 'oficial'
           AND (p.estado <> 'designada' OR d.activa = false)
        """
    )
    # Pericias recién designadas: el perito oficial tiene 3 días para aceptar o inhibirse.
    op.execute(
        """
        UPDATE designaciones_pericia d
           SET aceptacion = 'pendiente', aceptacion_vence_en = now() + interval '3 days'
          FROM pericias p
         WHERE p.id = d.pericia_id AND d.tipo = 'oficial' AND d.activa = true AND p.estado = 'designada'
        """
    )


def downgrade() -> None:
    for nombre, _ in reversed(COLUMNAS):
        op.drop_column("designaciones_pericia", nombre)
