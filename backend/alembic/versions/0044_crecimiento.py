"""Crecimiento: referidos entre despachos, trivia y ruleta con premios, y casos de la calculadora para la red de despachos.

Revision ID: 0044
Revises: 0043
"""
import sqlalchemy as sa
from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None

TS = lambda n, nulo=True: sa.Column(n, sa.DateTime(timezone=True), nullable=nulo)
ID = lambda: sa.Column("id", sa.Integer(), primary_key=True)
ORG = lambda nulo=False, borrar="CASCADE": sa.Column("organizacion_id", sa.Integer(), sa.ForeignKey("organizaciones.id", ondelete=borrar), nullable=nulo)
USR = lambda nulo=True, borrar="SET NULL": sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete=borrar), nullable=nulo)
B = lambda n: sa.Column(n, sa.Boolean(), nullable=False)
I = lambda n, nulo=False: sa.Column(n, sa.Integer(), nullable=nulo)


def upgrade() -> None:
    op.create_table("cx_config", ID(), B("juegos_activos"), B("ruleta_activa"), sa.Column("ruleta_permiso", sa.String(120)),
                    I("puntos_por_acierto"), I("preguntas_por_dia"), I("tope_puntos_dia_org"), I("tope_meses_anual"), B("referidos_activos"),
                    I("meses_referido"), I("tope_referidos_anual"), B("casos_activos"), TS("actualizado_en", False))
    op.create_table("cx_preguntas", ID(), sa.Column("clave", sa.String(40), unique=True), sa.Column("materia", sa.String(40), nullable=False),
                    sa.Column("texto", sa.String(400), nullable=False), sa.Column("opciones", sa.JSON(), nullable=False), I("correcta"),
                    sa.Column("explicacion", sa.String(800), nullable=False), B("activa"), TS("creado_en", False))
    op.create_table("cx_respuestas", ID(), USR(False, "CASCADE"), ORG(),
                    sa.Column("pregunta_id", sa.Integer(), sa.ForeignKey("cx_preguntas.id", ondelete="CASCADE"), nullable=False),
                    I("elegida"), B("correcta"), sa.Column("dia", sa.Date(), nullable=False), TS("creado_en", False),
                    sa.UniqueConstraint("usuario_id", "pregunta_id"))
    op.create_index("ix_cx_respuestas_usuario_id", "cx_respuestas", ["usuario_id"])
    op.create_index("ix_cx_respuestas_organizacion_id", "cx_respuestas", ["organizacion_id"])
    op.create_table("cx_movimientos", ID(), ORG(), USR(), sa.Column("origen", sa.String(12), nullable=False), I("puntos"),
                    sa.Column("detalle", sa.String(200)), sa.Column("dia", sa.Date(), nullable=False), TS("creado_en", False))
    op.create_index("ix_cx_movimientos_organizacion_id", "cx_movimientos", ["organizacion_id"])
    op.create_table("cx_premios", ID(), sa.Column("lugar", sa.String(8), nullable=False), sa.Column("etiqueta", sa.String(60), nullable=False),
                    sa.Column("tipo", sa.String(10), nullable=False), I("valor"), I("peso"), I("costo"), I("tope_mensual", True), I("orden"), B("activo"))
    op.create_table("cx_giros", ID(), ORG(), USR(), sa.Column("semana", sa.String(8), nullable=False),
                    sa.Column("premio_id", sa.Integer(), sa.ForeignKey("cx_premios.id", ondelete="SET NULL")),
                    sa.Column("etiqueta", sa.String(60), nullable=False), TS("creado_en", False), sa.UniqueConstraint("organizacion_id", "semana"))
    op.create_index("ix_cx_giros_creado_en", "cx_giros", ["creado_en"])
    op.create_table("cx_recompensas", ID(), ORG(), sa.Column("origen", sa.String(12), nullable=False), sa.Column("tipo", sa.String(10), nullable=False),
                    I("valor"), sa.Column("descripcion", sa.String(200), nullable=False), sa.Column("estado", sa.String(10), nullable=False),
                    sa.Column("cupon_id", sa.Integer(), sa.ForeignKey("cm_cupones.id", ondelete="SET NULL")),
                    sa.Column("periodo_id", sa.Integer(), sa.ForeignKey("periodos_suscripcion.id", ondelete="SET NULL")),
                    TS("creado_en", False), TS("aplicada_en"))
    op.create_index("ix_cx_recompensas_organizacion_id", "cx_recompensas", ["organizacion_id"])
    op.create_table("cx_invitaciones", ID(), sa.Column("organizacion_id", sa.Integer(), sa.ForeignKey("organizaciones.id", ondelete="CASCADE"), nullable=False, unique=True),
                    sa.Column("codigo", sa.String(12), nullable=False, unique=True), TS("creado_en", False))
    op.create_table("cx_referidos", ID(), sa.Column("referidor_id", sa.Integer(), sa.ForeignKey("organizaciones.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("referido_id", sa.Integer(), sa.ForeignKey("organizaciones.id", ondelete="CASCADE"), nullable=False, unique=True),
                    sa.Column("estado", sa.String(10), nullable=False), TS("creado_en", False), TS("premiado_en"))
    op.create_index("ix_cx_referidos_referidor_id", "cx_referidos", ["referidor_id"])
    op.create_table("cx_red", ID(), sa.Column("organizacion_id", sa.Integer(), sa.ForeignKey("organizaciones.id", ondelete="CASCADE"), nullable=False, unique=True),
                    B("activo"), sa.Column("estados", sa.JSON(), nullable=False), I("tope_mensual", True), TS("ultimo_en"), TS("actualizado_en", False))
    op.create_table("cx_casos", ID(), sa.Column("estado_mx", sa.String(4), nullable=False), ORG(True, "SET NULL"),
                    sa.Column("prospecto_id", sa.Integer(), sa.ForeignKey("ld_prospectos.id", ondelete="SET NULL")), TS("creado_en", False))
    op.create_index("ix_cx_casos_organizacion_id", "cx_casos", ["organizacion_id"])
    op.create_index("ix_cx_casos_creado_en", "cx_casos", ["creado_en"])


def downgrade() -> None:
    for t in ("cx_casos", "cx_red", "cx_referidos", "cx_invitaciones", "cx_recompensas", "cx_giros", "cx_premios", "cx_movimientos",
              "cx_respuestas", "cx_preguntas", "cx_config"):
        op.drop_table(t)
