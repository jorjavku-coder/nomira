"""panel de plataforma: administradores aparte, estado de la organización y soporte

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa


revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('organizaciones', sa.Column('estado', sa.String(20), server_default='activa', nullable=False))
    op.add_column('organizaciones', sa.Column('motivo_suspension', sa.String(300), nullable=True))
    op.create_table(
        'administradores_plataforma',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(254), nullable=False, unique=True),
        sa.Column('nombre', sa.String(200), nullable=False),
        sa.Column('hash_contrasena', sa.String(200), nullable=False),
        sa.Column('activo', sa.Boolean(), nullable=False),
        sa.Column('sesion_version', sa.Integer(), server_default='0', nullable=False),
        sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ultimo_acceso', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        'tickets_soporte',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organizacion_id', sa.Integer(), sa.ForeignKey('organizaciones.id'), nullable=False),
        sa.Column('asunto', sa.String(200), nullable=False),
        sa.Column('estado', sa.String(20), nullable=False),
        sa.Column('creado_por_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='SET NULL'), nullable=True),
        sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actualizado_en', sa.DateTime(timezone=True), nullable=False),
        sa.Column('leido_cliente', sa.Boolean(), nullable=False),
        sa.Column('leido_plataforma', sa.Boolean(), nullable=False),
    )
    op.create_index('ix_tickets_soporte_organizacion_id', 'tickets_soporte', ['organizacion_id'])
    op.create_index('ix_tickets_soporte_actualizado_en', 'tickets_soporte', ['actualizado_en'])
    op.create_table(
        'mensajes_soporte',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ticket_id', sa.Integer(), sa.ForeignKey('tickets_soporte.id', ondelete='CASCADE'), nullable=False),
        sa.Column('autor_tipo', sa.String(15), nullable=False),
        sa.Column('autor_nombre', sa.String(200), nullable=False),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='SET NULL'), nullable=True),
        sa.Column('admin_id', sa.Integer(), sa.ForeignKey('administradores_plataforma.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('texto', sa.Text(), nullable=False),
        sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_mensajes_soporte_ticket_id', 'mensajes_soporte', ['ticket_id'])


def downgrade() -> None:
    op.drop_table('mensajes_soporte')
    op.drop_table('tickets_soporte')
    op.drop_table('administradores_plataforma')
    op.drop_column('organizaciones', 'motivo_suspension')
    op.drop_column('organizaciones', 'estado')
