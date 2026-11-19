"""bitácora de correos enviados (bienvenida y recordatorios de vencimiento)

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa


revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'correos_enviados',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tipo', sa.String(40), nullable=False),
        sa.Column('organizacion_id', sa.Integer(), sa.ForeignKey('organizaciones.id', ondelete='CASCADE'),
                  nullable=True),
        sa.Column('periodo_id', sa.Integer(), sa.ForeignKey('periodos_suscripcion.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('llave', sa.String(80), nullable=True, unique=True),
        sa.Column('destinatarios', sa.String(1000), nullable=False),
        sa.Column('asunto', sa.String(300), nullable=False),
        sa.Column('estado', sa.String(20), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_correos_enviados_organizacion_id', 'correos_enviados', ['organizacion_id'])
    op.create_index('ix_correos_enviados_creado_en', 'correos_enviados', ['creado_en'])


def downgrade() -> None:
    op.drop_table('correos_enviados')
