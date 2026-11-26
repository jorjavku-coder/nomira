"""Vitrina de la cuenta demo (demo@nomirasoft.com): «Despacho Nomira» con 5 clientes y asuntos FICTICIOS para
presentar Nomira Connect a despachos. Una sola vez (si ya existe la primera clienta, no hace nada), así que
lo que el presentador cambie a mano se conserva.

Los clientes no tienen correo ni teléfono: su portal abre sin código (cómodo para presentar) y no se envía
ningún aviso a direcciones inventadas. No se crean avisos «enviados» falsos.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from .. import modulos
from ..agenda.base import hoy
from ..clientes import base as cl
from . import base as cb
from . import plantillas as pl

MARCA = "Rosa María Hernández Soto"
NOMBRES_VIEJOS = ("Despacho Piloto Nomira (datos ficticios)",)
NOMBRE = "Despacho Nomira"
ABOGADA = "Lic. Mariana Robles"


def sembrar(db: Session, email: str) -> bool:
    admin = db.scalar(select(m.Usuario).where(m.Usuario.email == email))
    if not admin:
        return False
    oid = admin.organizacion_id
    org = db.get(m.Organizacion, oid)
    if org.nombre in NOMBRES_VIEJOS:
        org.nombre = NOMBRE
    if admin.nombre == "Demo Nomira":  # en el portal el cliente ve «Abogado: …»
        admin.nombre = ABOGADA
    if db.scalar(select(m.CrCliente.id).where(m.CrCliente.organizacion_id == oid, m.CrCliente.nombre == MARCA)):
        db.commit()
        return False
    modulos.fijar(db, oid, "connect", contratado=True, activo=True)
    h, ahora = hoy(), m.ahora()

    def cliente(nombre, **kw):
        c = m.CrCliente(organizacion_id=oid, nombre=nombre, responsable_id=admin.id, creado_por_id=admin.id, origen="manual",
                        notas="Cliente ficticio de demostración.", **kw)
        db.add(c)
        db.flush()
        return c

    def asunto(c, titulo, numero, materia, tribunal, jurisdiccion="estatal", entidad="Estado de México", dias=120):
        a = m.AgAsunto(organizacion_id=oid, titulo=titulo, numero=numero, cr_cliente_id=c.id, materia=materia, tribunal=tribunal,
                       jurisdiccion=jurisdiccion, entidad=entidad, responsable_id=admin.id, estado="activo", creado_por_id=admin.id,
                       creado_en=ahora - timedelta(days=dias))
        db.add(a)
        db.flush()
        return a

    def seguimiento(a, base, actual, dias, notas=None, omitidas=(), estado_actual="actual", cerrar=False):
        """Avanza el seguimiento: etapas anteriores completadas con fechas escalonadas e historial con fechas reales."""
        s = cb.crear(db, a, pl.BASE[base]["nombre"], base, pl.BASE[base]["etapas"], admin)
        s.creado_en = ahora - timedelta(days=dias)
        for ev in db.scalars(select(m.CnEvento).where(m.CnEvento.seguimiento_id == s.id)):
            ev.creado_en = s.creado_en
        etapas = cb.etapas_de(db, s)
        notas = notas or {}
        paso = max(dias // max(actual, 1), 3)
        for i, e in enumerate(etapas):
            e.nota_publica = notas.get(e.nombre)
            if i in omitidas:
                e.estado, e.fecha = "omitida", None
            elif i < actual or cerrar:
                e.estado, e.fecha = "completada", h - timedelta(days=max(dias - paso * (i + 1), 1))
                cb.evento(db, s, "etapa", f"Etapa completada: {e.nombre}", e.nota_publica, True, admin).creado_en = \
                    ahora - timedelta(days=max(dias - paso * (i + 1), 1))
            elif i == actual:
                e.estado, e.fecha = estado_actual, h - timedelta(days=max(dias - paso * i, 1))
                cb.evento(db, s, "etapa", f"Nueva etapa: {e.nombre}", e.nota_publica or e.explicacion, True, admin).creado_en = \
                    ahora - timedelta(days=max(dias - paso * i, 1))
            else:
                e.estado, e.fecha = "pendiente", None
        s.visible_cliente, s.mostrar_audiencias = True, True
        if cerrar:
            s.estado = "cerrado"
            cb.evento(db, s, "estado", "El asunto concluyó", None, True, admin).creado_en = ahora - timedelta(days=2)
        db.flush()
        s.publico_actualizado_en = max(x.creado_en for x in db.scalars(select(m.CnEvento).where(m.CnEvento.seguimiento_id == s.id)))
        return s

    def revision(s, dias):
        s.ultima_revision_en, s.ultima_revision_por_id = ahora - timedelta(days=dias), admin.id
        cb.evento(db, s, "revision", "Su abogado revisó el expediente", None, True, admin).creado_en = ahora - timedelta(days=dias)

    def movimiento(s, dias, texto):
        s.ultimo_movimiento_fecha, s.ultimo_movimiento_texto = h - timedelta(days=dias), texto
        cb.evento(db, s, "movimiento", "Nuevo movimiento en su expediente", texto, True, admin).creado_en = ahora - timedelta(days=dias)

    def audiencia(a, dias, hora, titulo, lugar):
        db.add(m.AgEvento(organizacion_id=oid, asunto_id=a.id, tipo="audiencia", titulo=titulo, fecha=h + timedelta(days=dias), hora=hora,
                          lugar=lugar, prioridad="alta", responsable_id=admin.id, alertas=[3, 1], estado="pendiente", creado_por_id=admin.id))

    def mensaje(c, a, autor, texto, horas, motivo=None, estado=None):
        db.add(m.CnMensaje(organizacion_id=oid, cliente_id=c.id, asunto_id=a.id if a else None, autor=autor, motivo=motivo,
                           usuario_id=admin.id if autor == "despacho" else None, texto=texto,
                           estado=estado or ("enviado" if autor == "despacho" else "atendido"),
                           leido_en=ahora - timedelta(hours=horas - 1) if estado != "nuevo" else None, creado_en=ahora - timedelta(hours=horas)))

    def cargo(c, concepto, monto, vence_dias, pagado=None):
        g = m.CrCargo(organizacion_id=oid, cliente_id=c.id, concepto=concepto, monto=Decimal(monto), fecha=h - timedelta(days=60),
                      vence=h + timedelta(days=vence_dias), creado_por_id=admin.id)
        db.add(g)
        db.flush()
        if pagado:
            db.add(m.CrPago(organizacion_id=oid, cliente_id=c.id, cargo_id=g.id, folio=cl.siguiente_folio(db, oid), monto=Decimal(pagado),
                            fecha=h - timedelta(days=45), metodo="transferencia", referencia="Demo", registrado_por_id=admin.id))
            db.flush()

    # 1. Pensión ISSEMYM: en espera de resolución (el caso típico de «¿cómo va lo mío?»)
    rosa = cliente(MARCA, etiquetas=["Pensiones"])
    a1 = asunto(rosa, "Pensión por jubilación ISSEMYM", "TECA/1187/2026", "seguridad_social",
                "Tribunal Estatal de Conciliación y Arbitraje del Estado de México", dias=210)
    s1 = seguimiento(a1, "pensiones", 8, 200, {
        "Análisis de prestaciones": "Revisamos sus años de servicio y su salario base: le corresponde la pensión completa.",
        "Presentación de la demanda": "Presentamos su demanda ante el tribunal.",
        "Admisión": "El tribunal admitió su demanda."})
    movimiento(s1, 34, "Concluyó la etapa de pruebas; el asunto quedó listo para que el tribunal resuelva.")
    revision(s1, 3)
    s1.mensaje_publico = "Su expediente está completo. Estamos al pendiente de la resolución del tribunal y le avisaremos de inmediato."
    s1.mostrar_pagos = True
    cargo(rosa, "Honorarios: juicio de pensión (anticipo)", "6000", -50, pagado="6000")
    cargo(rosa, "Honorarios: juicio de pensión (pago final al resolverse)", "9000", 60)
    mensaje(rosa, a1, "cliente", "Buenos días, ¿ya hay noticias de mi pensión?", 120, "seguimiento")
    mensaje(rosa, a1, "despacho", "Buenos días, doña Rosa. Su asunto sigue en espera de resolución; el expediente está completo. "
            "En cuanto el tribunal resuelva le avisamos por aquí.", 118)

    # 2. Laboral: audiencia próxima y una pregunta sin responder
    carlos = cliente("Carlos Alberto Mendoza Ruiz", etiquetas=["Laboral"])
    a2 = asunto(carlos, "Mendoza Ruiz vs. Logística Express del Centro", "1452/2026", "laboral", "Tribunal Laboral de la Ciudad de México",
                entidad="Ciudad de México", dias=95)
    s2 = seguimiento(a2, "laboral", 5, 90, {
        "Conciliación": "No hubo acuerdo con la empresa en el Centro de Conciliación; seguimos con la demanda.",
        "Presentación de la demanda": "Presentamos su demanda por despido injustificado.",
        "Audiencias": "La audiencia preliminar ya tiene fecha. Le confirmaremos si necesita asistir."})
    movimiento(s2, 9, "El tribunal fijó fecha para la audiencia preliminar.")
    revision(s2, 1)
    audiencia(a2, 6, "10:00", "Audiencia preliminar", "Tribunal Laboral de la Ciudad de México, Sala 4")
    s2.mostrar_pagos = True
    cargo(carlos, "Honorarios: juicio laboral (anticipo)", "5000", -20, pagado="5000")
    cargo(carlos, "Honorarios: juicio laboral (segundo pago)", "5000", -4)
    mensaje(carlos, a2, "cliente", "Licenciada, ¿tengo que ir a la audiencia del próximo martes? ¿Qué debo llevar?", 3, "seguimiento", "nuevo")

    # 3. Familiar: el despacho necesita documentos (amarillo)
    laura = cliente("Laura Patricia Gómez Díaz", etiquetas=["Familiar"])
    a3 = asunto(laura, "Divorcio y pensión alimenticia", "873/2026", "familiar", "Juzgado Tercero Familiar de Tlalnepantla", dias=25)
    s3 = seguimiento(a3, "familiar", 1, 20, {
        "Integración de documentación": "Necesitamos su acta de matrimonio y las actas de nacimiento de sus hijos, en original."},
        estado_actual="atencion")
    s3.accion_cliente = "Traer al despacho el acta de matrimonio y las actas de nacimiento de sus hijos (originales). Lunes a viernes de 9:00 a 18:00."
    cb.evento(db, s3, "aviso", "Necesitamos algo de usted", s3.accion_cliente, True, admin).creado_en = ahora - timedelta(days=4)
    revision(s3, 4)
    mensaje(laura, a3, "cliente", "Ya conseguí las actas. ¿Puedo llevarlas el jueves por la tarde?", 20, "documentos", "nuevo")

    # 4. Amparo de una empresa: suspensión concedida y audiencia constitucional
    horizonte = cliente("Inmobiliaria Horizonte del Valle, S.A. de C.V.", tipo="moral", contacto="Ing. Patricia Salinas", etiquetas=["Empresa", "Amparo"])
    a4 = asunto(horizonte, "Amparo contra orden de clausura", "1290/2026", "amparo",
                "Juzgado Cuarto de Distrito en Materia Administrativa en la Ciudad de México", jurisdiccion="federal", entidad="Ciudad de México", dias=60)
    s4 = seguimiento(a4, "amparo", 5, 55, {
        "Suspensión": "El juzgado concedió la suspensión: la clausura no se ejecuta mientras se resuelve el amparo.",
        "Audiencias": "La audiencia constitucional está programada."})
    movimiento(s4, 6, "El juzgado señaló fecha para la audiencia constitucional.")
    revision(s4, 2)
    audiencia(a4, 14, "09:30", "Audiencia constitucional", "Juzgado Cuarto de Distrito en Materia Administrativa, CDMX")
    s4.mensaje_publico = "Buenas noticias: la suspensión sigue vigente. Su negocio puede operar con normalidad mientras se resuelve."
    s4.mostrar_pagos = True
    cargo(horizonte, "Iguala mensual — noviembre", "12000", -10, pagado="12000")
    cargo(horizonte, "Iguala mensual — diciembre", "12000", 20)
    mensaje(horizonte, a4, "cliente", "Gracias por la noticia de la suspensión. ¿Podemos agendar una llamada para revisar los siguientes pasos?", 50, "llamada")
    mensaje(horizonte, a4, "despacho", "Con gusto, ingeniera. Le llamamos mañana a las 11:00.", 46)

    # 5. Notarial: asunto concluido (así se ve un caso terminado)
    jorge = cliente("Jorge Luis Ramírez Torres", etiquetas=["Notarial"])
    a5 = asunto(jorge, "Compraventa de casa habitación en Metepec", "Escritura 48,215", "otra", "Notaría Pública (ficticia)", dias=75)
    a5.estado = "concluido"
    seguimiento(a5, "notarial", 7, 70, {"Firma": "Se firmó la escritura ante el notario.",
                                        "Entrega de documentación": "Le entregamos su testimonio inscrito en el Registro Público."}, cerrar=True)
    cargo(jorge, "Honorarios y gastos de escrituración", "18500", -30, pagado="18500")
    db.commit()
    return True
