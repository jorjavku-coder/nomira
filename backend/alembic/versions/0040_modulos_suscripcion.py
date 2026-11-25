"""Compra directa de módulos: suscripción mensual en Stripe.

Revision ID: 0040
Revises: 0039
"""
import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "md_suscripciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organizacion_id", sa.Integer(), sa.ForeignKey("organizaciones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("modulo", sa.String(30), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("precio", sa.Numeric(14, 2), nullable=False),
        sa.Column("iva", sa.Numeric(14, 2), nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("estado", sa.String(15), nullable=False),
        sa.Column("stripe_sesion", sa.String(120), nullable=True, unique=True),
        sa.Column("stripe_suscripcion", sa.String(120), nullable=True),
        sa.Column("modo", sa.String(10), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelada_en", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_md_suscripciones_organizacion_id", "md_suscripciones", ["organizacion_id"])
    op.create_index("ix_md_suscripciones_stripe_suscripcion", "md_suscripciones", ["stripe_suscripcion"])


def downgrade() -> None:
    op.drop_table("md_suscripciones")
