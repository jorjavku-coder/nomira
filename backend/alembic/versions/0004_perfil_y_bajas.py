"""foto de perfil y baja lógica de usuarios

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('usuarios', sa.Column('foto', sa.LargeBinary(), nullable=True))
    op.add_column('usuarios', sa.Column('eliminado_en', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('usuarios', 'eliminado_en')
    op.drop_column('usuarios', 'foto')
