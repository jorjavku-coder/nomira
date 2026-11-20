"""leads: enlace al aviso de privacidad del despacho

Revision ID: 0016
Revises: 0015
"""
from alembic import op
import sqlalchemy as sa


revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('ld_config', sa.Column('aviso_privacidad_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('ld_config', 'aviso_privacidad_url')
