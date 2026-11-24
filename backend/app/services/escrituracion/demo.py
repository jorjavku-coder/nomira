"""Escrituración de demostración (datos ficticios): activa el módulo en la demo y crea dos expedientes. Una sola vez."""
from __future__ import annotations

from datetime import datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from .. import modulos
from ..agenda.base import ZONA, hoy
from . import base as eb


def sembrar(db: Session, email: str = "admin@demo.local") -> bool:
    admin = db.scalar(select(m.Usuario).where(m.Usuario.email == email))
    if not admin:
        return False
    oid = admin.organizacion_id
    if db.scalar(select(m.OrganizacionModulo.id).where(m.OrganizacionModulo.organizacion_id == oid, m.OrganizacionModulo.modulo == "escrituracion")):
        return False
    modulos.fijar(db, oid, "escrituracion", contratado=True, activo=True)
    h = hoy()

    def expediente(acto, titulo, inmueble, partes, cita=None):
        e = m.EsExpediente(organizacion_id=oid, folio=eb.siguiente_folio(db, oid, h.year), acto=acto, titulo=titulo, inmueble=inmueble,
                           responsable_id=admin.id, creado_por_id=admin.id, cita_firma=cita, cita_lugar="Oficinas de la notaría (demo)" if cita else None,
                           notas="Expediente de demostración: datos ficticios.")
        db.add(e)
        db.flush()
        eb.crear_etapas(db, e)
        eb.agregar_requisitos(db, e.id, eb.plantilla_requisitos(acto))
        for rol, nombre, casado in partes:
            p = m.EsParte(expediente_id=e.id, rol=rol, nombre=nombre, casado=casado)
            db.add(p)
            db.flush()
            eb.agregar_requisitos(db, e.id, eb.requisitos_parte(p), p.id)
        db.flush()
        return e

    cita = datetime.combine(h + timedelta(days=6), time(11, 0), tzinfo=ZONA)
    e = expediente("compraventa", "Casa en Calle Ficticia 123", "Calle Ficticia 123, Col. Demo, Toluca, Estado de México",
                   [("comprador", "Juan Demo Ficticio", False), ("vendedor", "Laura Ficticia Ramírez", True)], cita)
    for r in db.scalars(select(m.EsRequisito).where(m.EsRequisito.expediente_id == e.id)):
        if r.clave in ("matrimonio", "domicilio"):
            continue  # faltan dos: el semáforo sale en rojo
        r.estado, r.origen, r.recibido_en = "validado", "notaria", m.ahora()
        r.validado_por_id, r.validado_en = admin.id, m.ahora()
        if r.vigencia_dias:
            r.expedido_en = h - timedelta(days=5)
            eb.calcular_vence(r)
    for x in db.scalars(select(m.EsHito).where(m.EsHito.expediente_id == e.id, m.EsHito.clave.in_(("documentos", "avaluo")))):
        x.estado, x.fecha, x.actualizado_en = "hecho", h - timedelta(days=3), m.ahora()
    expediente("testamento", "Testamento de Juan Demo Ficticio", None, [("testador", "Juan Demo Ficticio", False)])
    db.commit()
    return True
