"""Nomira Connect (fase 1): plantillas, seguimiento por asunto, portal del cliente y mensajes.

Revision ID: 0041
Revises: 0040
"""
import sqlalchemy as sa
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None

ORG = lambda: sa.Column("organizacion_id", sa.Integer(), sa.ForeignKey("organizaciones.id", ondelete="CASCADE"), nullable=False)
USR = lambda n: sa.Column(n, sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
TS = lambda n, nulo=True: sa.Column(n, sa.DateTime(timezone=True), nullable=nulo)


def upgrade() -> None:
    op.create_table("cn_plantillas", sa.Column("id", sa.Integer(), primary_key=True), ORG(),
                    sa.Column("nombre", sa.String(120), nullable=False), sa.Column("especialidad", sa.String(40), nullable=False),
                    sa.Column("etapas", sa.JSON(), nullable=False), USR("creado_por_id"), TS("creado_en", False), TS("actualizado_en", False))
    op.create_index("ix_cn_plantillas_organizacion_id", "cn_plantillas", ["organizacion_id"])
    op.create_table("cn_seguimientos", sa.Column("id", sa.Integer(), primary_key=True), ORG(),
                    sa.Column("asunto_id", sa.Integer(), sa.ForeignKey("ag_asuntos.id", ondelete="CASCADE"), nullable=False, unique=True),
                    sa.Column("plantilla_nombre", sa.String(120)), sa.Column("especialidad", sa.String(40)),
                    sa.Column("estado", sa.String(12), nullable=False), sa.Column("visible_cliente", sa.Boolean(), nullable=False),
                    sa.Column("mostrar_audiencias", sa.Boolean(), nullable=False), sa.Column("mostrar_pagos", sa.Boolean(), nullable=False),
                    sa.Column("mensaje_publico", sa.String(1000)), sa.Column("accion_cliente", sa.String(500)),
                    sa.Column("ultimo_movimiento_fecha", sa.Date()), sa.Column("ultimo_movimiento_texto", sa.String(500)),
                    TS("ultima_revision_en"), USR("ultima_revision_por_id"), TS("publico_actualizado_en"), USR("creado_por_id"), TS("creado_en", False))
    op.create_index("ix_cn_seguimientos_organizacion_id", "cn_seguimientos", ["organizacion_id"])
    op.create_table("cn_etapas", sa.Column("id", sa.Integer(), primary_key=True), ORG(),
                    sa.Column("seguimiento_id", sa.Integer(), sa.ForeignKey("cn_seguimientos.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("orden", sa.Integer(), nullable=False), sa.Column("nombre", sa.String(120), nullable=False),
                    sa.Column("explicacion", sa.String(500)), sa.Column("opcional", sa.Boolean(), nullable=False),
                    sa.Column("estado", sa.String(12), nullable=False), sa.Column("fecha", sa.Date()),
                    sa.Column("nota_publica", sa.String(500)), sa.Column("nota_interna", sa.String(1000)),
                    USR("actualizado_por_id"), TS("actualizado_en"))
    op.create_index("ix_cn_etapas_organizacion_id", "cn_etapas", ["organizacion_id"])
    op.create_index("ix_cn_etapas_seguimiento_id", "cn_etapas", ["seguimiento_id"])
    op.create_table("cn_eventos", sa.Column("id", sa.Integer(), primary_key=True), ORG(),
                    sa.Column("seguimiento_id", sa.Integer(), sa.ForeignKey("cn_seguimientos.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("tipo", sa.String(15), nullable=False), sa.Column("titulo", sa.String(200), nullable=False),
                    sa.Column("detalle", sa.String(1000)), sa.Column("visible_cliente", sa.Boolean(), nullable=False),
                    USR("usuario_id"), TS("creado_en", False))
    op.create_index("ix_cn_eventos_organizacion_id", "cn_eventos", ["organizacion_id"])
    op.create_index("ix_cn_eventos_seguimiento_id", "cn_eventos", ["seguimiento_id"])
    op.create_table("cn_accesos", sa.Column("id", sa.Integer(), primary_key=True), ORG(),
                    sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("cr_clientes.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("token_hash", sa.String(64), nullable=False, unique=True), sa.Column("token_pista", sa.String(8), nullable=False),
                    sa.Column("requiere_codigo", sa.Boolean(), nullable=False), TS("expira_en", False), TS("revocado_en"),
                    sa.Column("codigo_hash", sa.String(64)), TS("codigo_expira_en"), sa.Column("codigo_intentos", sa.Integer(), nullable=False),
                    TS("codigo_enviado_en"), sa.Column("codigos_enviados", sa.Integer(), nullable=False), TS("ultimo_uso_en"),
                    sa.Column("visitas", sa.Integer(), nullable=False), USR("creado_por_id"), TS("creado_en", False))
    op.create_index("ix_cn_accesos_organizacion_id", "cn_accesos", ["organizacion_id"])
    op.create_index("ix_cn_accesos_cliente_id", "cn_accesos", ["cliente_id"])
    op.create_table("cn_mensajes", sa.Column("id", sa.Integer(), primary_key=True), ORG(),
                    sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("cr_clientes.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("asunto_id", sa.Integer(), sa.ForeignKey("ag_asuntos.id", ondelete="SET NULL")),
                    sa.Column("autor", sa.String(10), nullable=False), USR("usuario_id"), sa.Column("motivo", sa.String(20)),
                    sa.Column("texto", sa.String(2000), nullable=False), sa.Column("estado", sa.String(12), nullable=False),
                    TS("leido_en"), TS("creado_en", False))
    op.create_index("ix_cn_mensajes_organizacion_id", "cn_mensajes", ["organizacion_id"])
    op.create_index("ix_cn_mensajes_cliente_id", "cn_mensajes", ["cliente_id"])
    op.create_index("ix_cn_mensajes_creado_en", "cn_mensajes", ["creado_en"])


def downgrade() -> None:
    for t in ("cn_mensajes", "cn_accesos", "cn_eventos", "cn_etapas", "cn_seguimientos", "cn_plantillas"):
        op.drop_table(t)
