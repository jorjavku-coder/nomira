"""evidencia: datos atómicos (tipo, tema, valor original/normalizado), contradicciones confirmadas
y solicitudes de documentos al cliente

Revision ID: 0012
Revises: 0011
"""
from alembic import op
import sqlalchemy as sa


revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('ev_hechos', sa.Column('tipo_dato', sa.String(length=20), nullable=False, server_default='otro'))
    op.add_column('ev_hechos', sa.Column('tema', sa.String(length=40), nullable=True))
    op.add_column('ev_hechos', sa.Column('valor_original', sa.String(length=300), nullable=True))
    op.add_column('ev_hechos', sa.Column('valor', sa.String(length=300), nullable=True))
    # Hechos ya existentes: se clasifican por lo que tienen; «Volver a leer» genera las propuestas nuevas.
    op.execute("UPDATE ev_hechos SET tipo_dato = CASE WHEN fecha IS NOT NULL THEN 'fecha_evento' "
               "WHEN importe IS NOT NULL THEN 'importe' ELSE 'otro' END, valor_original = fecha_texto")
    op.add_column('ev_hechos', sa.Column('atribucion', sa.String(length=200), nullable=True))
    op.add_column('ev_hechos', sa.Column('calidad', sa.String(length=10), nullable=True))
    op.add_column('ev_hechos', sa.Column('motivo_descarte', sa.String(length=30), nullable=True))
    op.add_column('ev_asuntos', sa.Column('decisiones_diferencias', sa.JSON(), nullable=True))
    for col, largo in (('ambito', 10), ('entidad_federativa', 40), ('municipio_distrito', 160), ('organo', 200),
                       ('expediente_judicial', 80)):
        op.add_column('ev_asuntos', sa.Column(col, sa.String(length=largo), nullable=True))
    # Si la jurisdicción capturada es exactamente una entidad federativa, se llena la entidad (ámbito
    # local). El texto original se conserva siempre en «jurisdiccion».
    import unicodedata
    entidades = ["Aguascalientes", "Baja California", "Baja California Sur", "Campeche", "Chiapas", "Chihuahua",
                 "Ciudad de México", "Coahuila", "Colima", "Durango", "Estado de México", "Guanajuato", "Guerrero", "Hidalgo",
                 "Jalisco", "Michoacán", "Morelos", "Nayarit", "Nuevo León", "Oaxaca", "Puebla", "Querétaro", "Quintana Roo",
                 "San Luis Potosí", "Sinaloa", "Sonora", "Tabasco", "Tamaulipas", "Tlaxcala", "Veracruz", "Yucatán", "Zacatecas"]
    llano = lambda t: "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn").strip(" .,")  # noqa: E731
    por_nombre = {llano(e): e for e in entidades} | {"cdmx": "Ciudad de México", "distrito federal": "Ciudad de México",
                                                     "edomex": "Estado de México"}
    con = op.get_bind()
    for aid, texto in con.execute(sa.text("SELECT id, jurisdiccion FROM ev_asuntos WHERE jurisdiccion IS NOT NULL")).all():
        e = por_nombre.get(llano(texto))
        if e:
            con.execute(sa.text("UPDATE ev_asuntos SET entidad_federativa = :e, ambito = 'local' WHERE id = :i"), {"e": e, "i": aid})
    op.add_column('ev_vinculos', sa.Column('relacion', sa.String(length=15), nullable=False, server_default='sin_evaluar'))
    op.add_column('ev_vinculos', sa.Column('relacion_por_id', sa.Integer(), nullable=True))
    op.add_column('ev_vinculos', sa.Column('relacion_en', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key('ev_vinculos_relacion_por_id_fkey', 'ev_vinculos', 'usuarios', ['relacion_por_id'], ['id'],
                          ondelete='SET NULL')

    op.create_table(
        'ev_solicitudes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organizacion_id', sa.Integer(), nullable=False),
        sa.Column('asunto_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=254), nullable=False),
        sa.Column('mensaje', sa.Text(), nullable=True),
        sa.Column('documentos', sa.JSON(), nullable=True),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('token_pista', sa.String(length=8), nullable=False),
        sa.Column('requiere_codigo', sa.Boolean(), nullable=False),
        sa.Column('max_archivos', sa.Integer(), nullable=False),
        sa.Column('archivos_recibidos', sa.Integer(), nullable=False),
        sa.Column('expira_en', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revocada_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revocada_por_id', sa.Integer(), nullable=True),
        sa.Column('codigo_hash', sa.String(length=64), nullable=True),
        sa.Column('codigo_expira_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('codigo_intentos', sa.Integer(), nullable=False),
        sa.Column('codigo_enviado_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('codigos_enviados', sa.Integer(), nullable=False),
        sa.Column('primer_acceso_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ultimo_acceso_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ultima_carga_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('creado_por_id', sa.Integer(), nullable=True),
        sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['asunto_id'], ['ev_asuntos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['creado_por_id'], ['usuarios.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organizacion_id'], ['organizaciones.id']),
        sa.ForeignKeyConstraint(['revocada_por_id'], ['usuarios.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )
    op.create_index(op.f('ix_ev_solicitudes_organizacion_id'), 'ev_solicitudes', ['organizacion_id'])
    op.create_index(op.f('ix_ev_solicitudes_asunto_id'), 'ev_solicitudes', ['asunto_id'])

    op.add_column('ev_documentos', sa.Column('solicitud_id', sa.Integer(), nullable=True))
    op.add_column('ev_documentos', sa.Column('aceptado_por_id', sa.Integer(), nullable=True))
    op.add_column('ev_documentos', sa.Column('aceptado_en', sa.DateTime(timezone=True), nullable=True))
    op.add_column('ev_documentos', sa.Column('solicitado_como', sa.String(length=200), nullable=True))
    op.add_column('ev_documentos', sa.Column('visibilidad', sa.String(length=15), nullable=False, server_default='interno'))
    op.add_column('ev_documentos', sa.Column('resumen_lectura', sa.JSON(), nullable=True))
    op.create_index(op.f('ix_ev_documentos_solicitud_id'), 'ev_documentos', ['solicitud_id'])
    op.create_foreign_key('ev_documentos_solicitud_id_fkey', 'ev_documentos', 'ev_solicitudes', ['solicitud_id'], ['id'],
                          ondelete='SET NULL')
    op.create_foreign_key('ev_documentos_aceptado_por_id_fkey', 'ev_documentos', 'usuarios', ['aceptado_por_id'], ['id'],
                          ondelete='SET NULL')


def downgrade():
    op.drop_constraint('ev_documentos_aceptado_por_id_fkey', 'ev_documentos', type_='foreignkey')
    op.drop_constraint('ev_documentos_solicitud_id_fkey', 'ev_documentos', type_='foreignkey')
    op.drop_index(op.f('ix_ev_documentos_solicitud_id'), table_name='ev_documentos')
    op.drop_column('ev_documentos', 'resumen_lectura')
    op.drop_column('ev_documentos', 'visibilidad')
    op.drop_column('ev_documentos', 'solicitado_como')
    op.drop_column('ev_documentos', 'aceptado_en')
    op.drop_column('ev_documentos', 'aceptado_por_id')
    op.drop_column('ev_documentos', 'solicitud_id')
    op.drop_index(op.f('ix_ev_solicitudes_asunto_id'), table_name='ev_solicitudes')
    op.drop_index(op.f('ix_ev_solicitudes_organizacion_id'), table_name='ev_solicitudes')
    op.drop_table('ev_solicitudes')
    op.drop_constraint('ev_vinculos_relacion_por_id_fkey', 'ev_vinculos', type_='foreignkey')
    for col in ('relacion_en', 'relacion_por_id', 'relacion'):
        op.drop_column('ev_vinculos', col)
    for col in ('expediente_judicial', 'organo', 'municipio_distrito', 'entidad_federativa', 'ambito', 'decisiones_diferencias'):
        op.drop_column('ev_asuntos', col)
    for col in ('motivo_descarte', 'calidad', 'atribucion'):
        op.drop_column('ev_hechos', col)
    op.drop_column('ev_hechos', 'valor')
    op.drop_column('ev_hechos', 'valor_original')
    op.drop_column('ev_hechos', 'tema')
    op.drop_column('ev_hechos', 'tipo_dato')
