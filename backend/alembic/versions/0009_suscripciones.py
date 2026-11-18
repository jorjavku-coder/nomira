"""periodos de suscripción de los clientes (prueba, mensual, semestral, anual)

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa


revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'periodos_suscripcion',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organizacion_id', sa.Integer(), sa.ForeignKey('organizaciones.id'), nullable=False),
        sa.Column('plan', sa.String(15), nullable=False),
        sa.Column('inicio', sa.Date(), nullable=False),
        sa.Column('fin', sa.Date(), nullable=False),
        sa.Column('monto', sa.Numeric(12, 2), nullable=True),
        sa.Column('pagado', sa.Boolean(), nullable=False),
        sa.Column('pagado_en', sa.Date(), nullable=True),
        sa.Column('nota', sa.String(500), nullable=True),
        sa.Column('creado_por_id', sa.Integer(),
                  sa.ForeignKey('administradores_plataforma.id', ondelete='SET NULL'), nullable=True),
        sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_periodos_suscripcion_organizacion_id', 'periodos_suscripcion', ['organizacion_id'])


def downgrade() -> None:
    op.drop_table('periodos_suscripcion')
