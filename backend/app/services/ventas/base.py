"""Ventas de Nomira (CRM interno): catálogos, alta de prospectos desde el sitio y sincronización con Cotizaciones."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ... import models as m

ETAPAS = [  # clave, nombre, probabilidad de cierre (%)
    ("nuevo", "Nuevo", 10), ("contactado", "Contactado", 20), ("demo", "Demo agendada", 40), ("propuesta", "Propuesta enviada", 60),
    ("negociacion", "Negociación", 80), ("ganado", "Ganado", 100), ("perdido", "Perdido", 0)]
ABIERTAS = [e[0] for e in ETAPAS[:5]]
ORDEN = {e[0]: i for i, e in enumerate(ETAPAS)}
NOMBRE_ETAPA = {e[0]: e[1] for e in ETAPAS}
PROB = {e[0]: e[2] for e in ETAPAS}
CANALES = {"facebook": "Facebook / Instagram", "google": "Google Ads", "linkedin": "LinkedIn", "correo": "Correo masivo", "evento": "Evento o congreso",
           "referidos": "Programa de referidos", "sitio": "Sitio web", "otro": "Otro"}
ORIGENES = {"sitio": "Formulario del sitio", "campana": "Campaña", "referido": "Referido", "evento": "Evento", "prospeccion": "Prospección (llamada o correo en frío)",
            "redes": "Redes sociales", "otro": "Otro"}
TIPOS = {"llamada": "Llamada", "correo": "Correo", "whatsapp": "WhatsApp", "reunion": "Reunión", "demo": "Demo", "nota": "Nota", "tarea": "Tarea", "sistema": "Sistema"}
MOTIVOS = {"precio": "Precio", "sin_respuesta": "Dejó de responder", "competencia": "Eligió otra opción", "no_es_momento": "No es el momento",
           "no_aplica": "No es su perfil", "otro": "Otro"}
COT_PROPUESTA = ("enviada", "vista", "aceptada", "pendiente_pago")
COT_GANADA = ("pagada",)


def actividad(db: Session, contacto_id: int, oportunidad_id: int | None, tipo: str, titulo: str, detalle: str | None = None,
              admin_id: int | None = None, vence_en: datetime | None = None, asignado_id: int | None = None) -> m.VtActividad:
    a = m.VtActividad(contacto_id=contacto_id, oportunidad_id=oportunidad_id, tipo=tipo, titulo=titulo[:200], detalle=detalle,
                      creado_por_id=admin_id, vence_en=vence_en, asignado_id=asignado_id,
                      completada_en=None if vence_en else m.ahora())
    db.add(a)
    if oportunidad_id:
        o = db.get(m.VtOportunidad, oportunidad_id)
        if o:
            o.ultima_actividad_en = m.ahora()
    return a


def mover(db: Session, o: m.VtOportunidad, etapa: str, admin_id: int | None, motivo: str | None = None, nota: str | None = None,
          automatico: str | None = None) -> None:
    if etapa == o.etapa:
        return
    antes = o.etapa
    o.etapa = etapa
    if o.solicitud_id and etapa != "nuevo":  # la solicitud del sitio queda atendida
        sol = db.get(m.Solicitud, o.solicitud_id)
        if sol and sol.estado == "nueva":
            sol.estado = "atendida"
    if etapa in ("ganado", "perdido"):
        o.cerrada_en = o.cerrada_en or m.ahora()
        o.motivo_perdida = motivo if etapa == "perdido" else None
        o.nota_cierre = nota
        for t in db.scalars(select(m.VtActividad).where(m.VtActividad.oportunidad_id == o.id, m.VtActividad.completada_en.is_(None))):
            t.completada_en, t.resultado = m.ahora(), "Cerrada al cerrar la oportunidad"
    else:
        o.cerrada_en, o.motivo_perdida, o.nota_cierre = None, None, None
    texto = f"{NOMBRE_ETAPA[antes]} → {NOMBRE_ETAPA[etapa]}" + (f" ({MOTIVOS.get(motivo, motivo)})" if motivo else "")
    actividad(db, o.contacto_id, o.id, "sistema", f"Etapa: {texto}", automatico or nota, admin_id)


def sincronizar(db: Session, oportunidades: list[m.VtOportunidad] | None = None) -> int:
    """Avanza las oportunidades según sus cotizaciones: propuesta enviada al enviarse, ganado al pagarse."""
    q = select(m.CmCotizacion).where(m.CmCotizacion.oportunidad_id.is_not(None))
    if oportunidades is not None:
        ids = [o.id for o in oportunidades]
        if not ids:
            return 0
        q = q.where(m.CmCotizacion.oportunidad_id.in_(ids))
    cambios = 0
    por_op: dict[int, list[m.CmCotizacion]] = {}
    for c in db.scalars(q):
        por_op.setdefault(c.oportunidad_id, []).append(c)
    for oid, cots in por_op.items():
        o = db.get(m.VtOportunidad, oid)
        if not o:
            continue
        org = next((c.organizacion_id for c in cots if c.organizacion_id), None)
        if org and not o.organizacion_id:
            o.organizacion_id = org
            ct = db.get(m.VtContacto, o.contacto_id)
            if ct and not ct.organizacion_id:
                ct.organizacion_id = org
        if o.etapa in ("ganado", "perdido"):
            continue
        pagada = next((c for c in cots if c.estado in COT_GANADA), None)
        if pagada:
            mover(db, o, "ganado", None, automatico=f"Cotización {pagada.folio} pagada.")
            cambios += 1
        elif ORDEN[o.etapa] < ORDEN["propuesta"] and any(c.estado in COT_PROPUESTA for c in cots):
            c = next(c for c in cots if c.estado in COT_PROPUESTA)
            mover(db, o, "propuesta", None, automatico=f"Cotización {c.folio} enviada al prospecto.")
            cambios += 1
    return cambios


def desde_solicitud(db: Session, sol: m.Solicitud) -> m.VtOportunidad | None:
    """Cada solicitud del sitio entra a Ventas como oportunidad nueva (una sola vez), con una tarea de primer contacto."""
    if db.scalar(select(m.VtOportunidad.id).where(m.VtOportunidad.solicitud_id == sol.id)):
        return None
    ct = db.scalar(select(m.VtContacto).where(func.lower(m.VtContacto.email) == sol.email.lower()).limit(1)) if sol.email else None
    if ct is None:
        ct = m.VtContacto(nombre=sol.nombre, despacho=sol.empresa, email=sol.email, telefono=sol.telefono, origen="sitio",
                          notas=f"Volumen indicado: {sol.expedientes_mes} expedientes al mes." if sol.expedientes_mes else None)
        db.add(ct)
        db.flush()
    o = m.VtOportunidad(contacto_id=ct.id, titulo=f"{'Suscripción' if sol.tipo == 'suscripcion' else 'Informes'} · {sol.empresa or sol.nombre}"[:200],
                        etapa="nuevo", origen="sitio", solicitud_id=sol.id, propietario_id=ct.propietario_id)
    db.add(o)
    db.flush()
    actividad(db, ct.id, o.id, "nota", "Llegó una solicitud desde el sitio", sol.mensaje)
    actividad(db, ct.id, o.id, "tarea", "Primer contacto con el prospecto", None, vence_en=m.ahora() + timedelta(hours=24), asignado_id=ct.propietario_id)
    return o


def importar_solicitudes(db: Session) -> int:
    ya = select(m.VtOportunidad.solicitud_id).where(m.VtOportunidad.solicitud_id.is_not(None))
    n = 0
    for s in db.scalars(select(m.Solicitud).where(m.Solicitud.id.not_in(ya)).order_by(m.Solicitud.id)):
        if desde_solicitud(db, s):
            n += 1
    return n


def dinero(v) -> str | None:
    return None if v is None else str(Decimal(v).quantize(Decimal("0.01")))
