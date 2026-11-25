"""Calendarios oficiales que se actualizan solos (primero: Poder Judicial del Estado de México).

Revision ID: 0039
Revises: 0038
"""
import sqlalchemy as sa
from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ag_calendarios", sa.Column("oficial", sa.String(20), nullable=True))
    op.add_column("ag_calendarios", sa.Column("sincronizado_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ag_calendarios", sa.Column("sincronizacion_error", sa.String(300), nullable=True))
    op.add_column("ag_dias", sa.Column("origen", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("ag_dias", "origen")
    op.drop_column("ag_calendarios", "sincronizacion_error")
    op.drop_column("ag_calendarios", "sincronizado_en")
    op.drop_column("ag_calendarios", "oficial")
