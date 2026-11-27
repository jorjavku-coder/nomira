"""Publica los precios completos en el sitio (página /precios con carrito). Se cambia desde Comercial > Configuración.

Revision ID: 0045
Revises: 0044
"""
from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE cm_config SET precios_publicos = 'completos'")


def downgrade() -> None:
    op.execute("UPDATE cm_config SET precios_publicos = 'ocultos' WHERE precios_publicos = 'completos'")
