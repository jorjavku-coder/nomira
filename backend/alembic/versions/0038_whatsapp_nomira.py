"""WhatsApp de Nomira: consentimiento de avisos y ventana de 24 h por contacto de Ventas.

Revision ID: 0038
Revises: 0037
"""
import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("solicitudes", sa.Column("acepta_whatsapp", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("vt_contactos", sa.Column("acepta_whatsapp", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("vt_contactos", sa.Column("whatsapp_ultimo_entrante", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("vt_contactos", "whatsapp_ultimo_entrante")
    op.drop_column("vt_contactos", "acepta_whatsapp")
    op.drop_column("solicitudes", "acepta_whatsapp")
