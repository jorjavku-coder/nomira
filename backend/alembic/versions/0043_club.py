"""Club Nomira: aliados, beneficios, usos (métricas), credenciales y solicitudes de empresas.

Revision ID: 0043
Revises: 0042
"""
import sqlalchemy as sa
from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None

TS = lambda n, nulo=True: sa.Column(n, sa.DateTime(timezone=True), nullable=nulo)


def upgrade() -> None:
    op.create_table("al_aliados", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("nombre", sa.String(200), nullable=False),
                    sa.Column("giro", sa.String(120)), sa.Column("sitio", sa.String(300)), sa.Column("contacto_nombre", sa.String(200)),
                    sa.Column("contacto_email", sa.String(254)), sa.Column("contacto_telefono", sa.String(30)),
                    sa.Column("estado", sa.String(12), nullable=False), sa.Column("notas", sa.Text()), sa.Column("logo", sa.LargeBinary()),
                    TS("logo_actualizado"), TS("creado_en", False))
    op.create_table("al_beneficios", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("aliado_id", sa.Integer(), sa.ForeignKey("al_aliados.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("titulo", sa.String(150), nullable=False), sa.Column("resumen", sa.String(80), nullable=False),
                    sa.Column("descripcion", sa.Text()), sa.Column("categoria", sa.String(20), nullable=False),
                    sa.Column("canje", sa.String(12), nullable=False), sa.Column("codigo", sa.String(60)), sa.Column("enlace", sa.String(500)),
                    sa.Column("condiciones", sa.Text()), sa.Column("cobertura", sa.JSON()), sa.Column("vigente_desde", sa.Date()),
                    sa.Column("vigente_hasta", sa.Date()), sa.Column("destacado", sa.Boolean(), nullable=False),
                    sa.Column("estado", sa.String(12), nullable=False), TS("creado_en", False), TS("actualizado_en", False))
    op.create_index("ix_al_beneficios_aliado_id", "al_beneficios", ["aliado_id"])
    op.create_table("al_usos", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("beneficio_id", sa.Integer(), sa.ForeignKey("al_beneficios.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("organizacion_id", sa.Integer(), sa.ForeignKey("organizaciones.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
                    sa.Column("tipo", sa.String(10), nullable=False), sa.Column("dia", sa.Date(), nullable=False), TS("creado_en", False))
    op.create_index("ix_al_usos_beneficio_id", "al_usos", ["beneficio_id"])
    op.create_index("ix_al_usos_organizacion_id", "al_usos", ["organizacion_id"])
    op.create_index("ux_al_usos_dia", "al_usos", ["beneficio_id", "usuario_id", "tipo", "dia"], unique=True)
    op.create_table("al_credenciales", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, unique=True),
                    sa.Column("codigo", sa.String(20), nullable=False, unique=True), TS("creado_en", False))
    op.create_table("al_solicitudes", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("empresa", sa.String(200), nullable=False),
                    sa.Column("giro", sa.String(120)), sa.Column("nombre", sa.String(200), nullable=False),
                    sa.Column("email", sa.String(254), nullable=False), sa.Column("telefono", sa.String(40)),
                    sa.Column("propuesta", sa.String(2000)), sa.Column("estado", sa.String(12), nullable=False),
                    sa.Column("nota", sa.String(2000)), sa.Column("ip", sa.String(60)), TS("creado_en", False))


def downgrade() -> None:
    for t in ("al_solicitudes", "al_credenciales", "al_usos", "al_beneficios", "al_aliados"):
        op.drop_table(t)
