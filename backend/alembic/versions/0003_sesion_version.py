"""versión de sesión por usuario (revoca tokens al cambiar contraseña o desactivar)

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('usuarios', sa.Column('sesion_version', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('usuarios', 'sesion_version')
