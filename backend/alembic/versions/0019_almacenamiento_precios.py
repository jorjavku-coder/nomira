"""Costo de almacenamiento (Render) en Comercial y ajuste de precios por Academia LMS.

Los ajustes de precios SOLO se aplican si el valor sigue siendo el inicial (nunca pisa lo que
Nomira ya cambió) y quedan en el historial de precios.

Revision ID: 0019
Revises: 0018
"""
from alembic import op
import sqlalchemy as sa


revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None

# (tabla, clave, campo, valor_inicial, valor_nuevo)
AJUSTES = [
    ("cm_precios", "modulo:academia", "precio_mensual", "470.00", "590.00"),
    ("cm_paquetes", "basico", "almacenamiento_gb", "20", "10"),
    ("cm_paquetes", "medio", "almacenamiento_gb", "100", "30"),
    ("cm_paquetes", "premium", "almacenamiento_gb", "250", "75"),
]


def upgrade() -> None:
    op.add_column('cm_config', sa.Column('costo_gb_usd', sa.Numeric(8, 4), server_default='0.25', nullable=False))
    op.add_column('cm_config', sa.Column('tipo_cambio', sa.Numeric(8, 4), server_default='19', nullable=False))
    op.add_column('cm_config', sa.Column('margen_almacenamiento_pct', sa.Numeric(6, 2), server_default='150', nullable=False))
    op.add_column('cm_config', sa.Column('disco_gb', sa.Integer(), server_default='5', nullable=False))
    con = op.get_bind()

    def historial(entidad, eid, campo, antes, despues):
        con.execute(sa.text("INSERT INTO cm_cambios_precio (entidad, entidad_id, campo, antes, despues, creado_en) "
                            "VALUES (:e, :i, :c, :a, :d, now())"), {"e": entidad, "i": eid, "c": campo, "a": antes, "d": despues})

    for tabla, clave, campo, ini, nuevo in AJUSTES:
        fila = con.execute(sa.text(f"SELECT id, {campo} FROM {tabla} WHERE clave = :k"), {"k": clave}).first()
        if fila and str(fila[1]) in (ini, ini.split(".")[0]):
            con.execute(sa.text(f"UPDATE {tabla} SET {campo} = :v WHERE id = :i"), {"v": nuevo, "i": fila[0]})
            historial("paquete" if tabla == "cm_paquetes" else "precio", fila[0], campo, ini, nuevo)
    # Curso propio adicional de Academia: se activa con precio sugerido si seguía sin precio.
    fila = con.execute(sa.text("SELECT id, precio_mensual, activo FROM cm_precios WHERE clave = 'curso_adicional'")).first()
    if fila and float(fila[1]) == 0 and not fila[2]:
        con.execute(sa.text("UPDATE cm_precios SET precio_mensual = 99, activo = true WHERE id = :i"), {"i": fila[0]})
        historial("precio", fila[0], "precio_mensual", "0.00", "99.00")
        historial("precio", fila[0], "activo", "False", "True")


def downgrade() -> None:
    for c in ('disco_gb', 'margen_almacenamiento_pct', 'tipo_cambio', 'costo_gb_usd'):
        op.drop_column('cm_config', c)
