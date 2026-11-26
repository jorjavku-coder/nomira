"""Nomira Connect (fase 2): avisos automáticos al cliente, actualizaciones preventivas y preferencias.

Revision ID: 0042
Revises: 0041
"""
import sqlalchemy as sa
from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cn_seguimientos", sa.Column("avisos", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("cn_seguimientos", sa.Column("preventiva_dias", sa.Integer(), nullable=True))
    op.add_column("cn_seguimientos", sa.Column("ultima_preventiva_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column("cn_accesos", sa.Column("origen", sa.String(10), nullable=False, server_default="manual"))
    op.create_table(
        "cn_config", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organizacion_id", sa.Integer(), sa.ForeignKey("organizaciones.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("avisos_activos", sa.Boolean(), nullable=False), sa.Column("canal_correo", sa.Boolean(), nullable=False),
        sa.Column("canal_whatsapp", sa.Boolean(), nullable=False), sa.Column("preventiva_dias", sa.Integer(), nullable=False),
        sa.Column("recordar_audiencias", sa.Boolean(), nullable=False), sa.Column("wa_plantilla", sa.String(120)),
        sa.Column("wa_idioma", sa.String(10), nullable=False), sa.Column("wa_aprobada", sa.Boolean(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False))
    op.create_table(
        "cn_preferencias", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organizacion_id", sa.Integer(), sa.ForeignKey("organizaciones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("cr_clientes.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("correo", sa.Boolean(), nullable=False), sa.Column("whatsapp", sa.Boolean(), nullable=False),
        sa.Column("whatsapp_consentido_en", sa.DateTime(timezone=True)), sa.Column("whatsapp_medio", sa.String(20)),
        sa.Column("actualizado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_cn_preferencias_organizacion_id", "cn_preferencias", ["organizacion_id"])
    op.create_table(
        "cn_avisos", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organizacion_id", sa.Integer(), sa.ForeignKey("organizaciones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("cr_clientes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seguimiento_id", sa.Integer(), sa.ForeignKey("cn_seguimientos.id", ondelete="SET NULL")),
        sa.Column("tipo", sa.String(15), nullable=False), sa.Column("canal", sa.String(10), nullable=False),
        sa.Column("llave", sa.String(120), nullable=False, unique=True), sa.Column("datos", sa.JSON(), nullable=False),
        sa.Column("resumen", sa.String(300), nullable=False), sa.Column("estado", sa.String(12), nullable=False),
        sa.Column("motivo", sa.String(300)), sa.Column("intentos", sa.Integer(), nullable=False),
        sa.Column("programado_en", sa.DateTime(timezone=True), nullable=False), sa.Column("enviado_en", sa.DateTime(timezone=True)),
        sa.Column("referencia", sa.String(120)),
        sa.Column("creado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False))
    for c in ("organizacion_id", "cliente_id", "seguimiento_id", "programado_en"):
        op.create_index(f"ix_cn_avisos_{c}", "cn_avisos", [c])


def downgrade() -> None:
    for t in ("cn_avisos", "cn_preferencias", "cn_config"):
        op.drop_table(t)
    op.drop_column("cn_accesos", "origen")
    for c in ("ultima_preventiva_en", "preventiva_dias", "avisos"):
        op.drop_column("cn_seguimientos", c)
