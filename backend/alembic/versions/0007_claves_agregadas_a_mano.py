"""marca de claves agregadas a mano en el catálogo (claves faltantes)

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa


revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('catalogo_entradas', sa.Column('agregada_manual', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('catalogo_entradas', 'agregada_manual')
