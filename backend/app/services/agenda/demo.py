"""Datos de demostración de Nomira Agenda Jurídica (ficticios). Se crean una sola vez."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from .. import modulos
from . import base
from .dias import Calendario, calcular


def sembrar(db: Session, email: str = "admin@demo.local") -> bool:
    admin = db.scalar(select(m.Usuario).where(m.Usuario.email == email))
    if not admin:
        return False
    oid = admin.organizacion_id
    if db.scalar(select(m.OrganizacionModulo.id).where(m.OrganizacionModulo.organizacion_id == oid, m.OrganizacionModulo.modulo == "agenda")):
        return False
    modulos.fijar(db, oid, "agenda", contratado=True, activo=True)
    analista = db.scalar(select(m.Usuario).where(m.Usuario.organizacion_id == oid, m.Usuario.rol == "analista")) or admin
    hoy = base.hoy()
    cal = m.AgCalendario(organizacion_id=oid, nombre="Tribunal Laboral Ficticio (demostración)", jurisdiccion="estatal", entidad="Ciudad de México",
                         fuente="Ejemplo: capture aquí la circular o acuerdo oficial del tribunal.", dias_semana_inhabiles=[5, 6], incluir_descanso_lft=True)
    db.add(cal)
    db.flush()
    db.add(m.AgDia(calendario_id=cal.id, fecha=hoy + timedelta(days=9), motivo="Suspensión de labores (ejemplo ficticio)", creado_por_id=admin.id))
    conf = base.config(db, oid)
    conf.calendario_id = cal.id
    a1 = m.AgAsunto(organizacion_id=oid, titulo="Ruiz Ficticio vs. Comercializadora Demo", numero="1450/2026", jurisdiccion="estatal",
                    entidad="Ciudad de México", tribunal="Tribunal Laboral Ficticio", materia="laboral", calendario_id=cal.id,
                    responsable_id=analista.id, creado_por_id=admin.id, actualizado_en=m.ahora())
    a2 = m.AgAsunto(organizacion_id=oid, titulo="Amparo indirecto Demo", numero="88/2026", jurisdiccion="federal", tribunal="Juzgado de Distrito Ficticio",
                    materia="amparo", responsable_id=admin.id, creado_por_id=admin.id, actualizado_en=m.ahora())
    a3 = m.AgAsunto(organizacion_id=oid, titulo="Divorcio incausado Demo", numero="512/2026", jurisdiccion="estatal",
                    entidad="Estado de México", tribunal="Juzgado Primero Familiar de Toluca", materia="familiar",
                    responsable_id=admin.id, creado_por_id=admin.id, actualizado_en=m.ahora(),
                    notas="Ejemplo de asunto ante el Poder Judicial del Estado de México: vea los accesos a sus sistemas en esta ficha.")
    db.add_all([a1, a2, a3])
    db.flush()
    notif = hoy - timedelta(days=3)
    act = m.AgActuacion(organizacion_id=oid, asunto_id=a1.id, fecha=notif - timedelta(days=1), tipo="acuerdo",
                        descripcion="Acuerdo que admite la demanda y ordena emplazar (ejemplo)", notificada_en=notif, creado_por_id=admin.id)
    db.add(act)
    db.flush()
    r = calcular(base.calendario(db, cal.id, oid), notif, 10, "habiles", "dia_habil_siguiente")
    r["calendario_id"], r["ajuste_manual"] = cal.id, None
    db.add_all([
        m.AgEvento(organizacion_id=oid, asunto_id=a1.id, actuacion_id=act.id, tipo="plazo", titulo="Contestar demanda (ejemplo)",
                   fecha=date.fromisoformat(r["vence"]),
                   prioridad="critica", responsable_id=analista.id, apoyo_ids=[admin.id], calculo=r, creado_por_id=admin.id),
        m.AgEvento(organizacion_id=oid, asunto_id=a1.id, tipo="audiencia", titulo="Audiencia preliminar", fecha=hoy, hora="11:00", duracion_min=90,
                   enlace="https://meet.google.com/abc-defg-hij", prioridad="alta", responsable_id=admin.id, creado_por_id=admin.id),
        m.AgEvento(organizacion_id=oid, asunto_id=a2.id, tipo="plazo", titulo="Desahogar vista (ejemplo)", fecha=hoy - timedelta(days=1),
                   prioridad="alta", responsable_id=admin.id, creado_por_id=admin.id),
        m.AgEvento(organizacion_id=oid, asunto_id=a2.id, tipo="actividad", titulo="Revisar lista de acuerdos", fecha=hoy + timedelta(days=2),
                   creado_por_id=admin.id),
    ])
    db.commit()
    return True


def sembrar_estrados(db: Session, email: str = "admin@demo.local") -> bool:
    """Vigilancia de estrados de ejemplo (sin publicaciones: esas las encuentra el cotejo o la revisión). Se crea una sola vez."""
    admin = db.scalar(select(m.Usuario).where(m.Usuario.email == email))
    if not admin or db.scalar(select(m.AgVigilancia.id).where(m.AgVigilancia.organizacion_id == admin.organizacion_id)):
        return False
    oid = admin.organizacion_id
    a = db.scalar(select(m.AgAsunto).where(m.AgAsunto.organizacion_id == oid, m.AgAsunto.titulo == "Nulidad Demo vs. Ayuntamiento Ficticio"))
    if a is None:
        a = m.AgAsunto(organizacion_id=oid, titulo="Nulidad Demo vs. Ayuntamiento Ficticio", numero="JA-1234/2026", jurisdiccion="estatal",
                       entidad="Estado de México", tribunal="TRIJAEM · Primera Sala Regional", materia="administrativo",
                       responsable_id=admin.id, creado_por_id=admin.id, actualizado_en=m.ahora())
        db.add(a)
        db.flush()
    db.add(m.AgVigilancia(organizacion_id=oid, asunto_id=a.id, fuente="trijaem", expediente="JA-1234/2026", sala="Primera Sala Regional Toluca",
                          creado_por_id=admin.id))
    amparo = db.scalar(select(m.AgAsunto).where(m.AgAsunto.organizacion_id == oid, m.AgAsunto.titulo == "Amparo indirecto Demo"))
    if amparo:  # expediente federal: se revisa en la «Revisión diaria del PJF»
        db.add(m.AgVigilancia(organizacion_id=oid, asunto_id=amparo.id, fuente="pjf", circuito="1", id_sala="10", expediente="88/2026",
                              sala="Juzgado Primero de Distrito en Materia Administrativa en la Ciudad de México", creado_por_id=admin.id))
    db.commit()
    return True
