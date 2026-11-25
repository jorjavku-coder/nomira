"""Cuenta piloto de demostración (demo@nomirasoft.com) y reinicio de la plataforma a ceros.

- ``sembrar_piloto``: crea el despacho piloto con datos ficticios en TODOS los módulos, usando los mismos sembradores
  de la demo. La contraseña nunca se guarda en el repositorio: viene de ``PILOTO_CONTRASENA`` o se escribe al correr.
- ``reiniciar``: borra todos los despachos (con sus archivos) y los datos de la plataforma ligados a personas o a la
  operación. Conserva: administradores del panel, textos legales, precios, paquetes, cupones, ejecutivos y cambios de
  precio, biblioteca de tesis, cursos de Nomira Academia y días inhábiles.
"""
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .. import models as m
from .plataforma import borrar_archivos, eliminar_organizacion

PILOTO_EMAIL = "demo@nomirasoft.com"
PILOTO_DESPACHO = "Despacho Piloto Nomira (datos ficticios)"

# Datos de la plataforma que no dependen de un despacho y se borran al reiniciar (personas, ventas, bitácoras).
_GLOBALES = ("solicitudes", "vt_actividades", "vt_oportunidades", "vt_contactos", "vt_campanas", "cm_pagos", "cm_eventos", "cm_eventos_stripe",
             "af_eventos_webhook", "ld_eventos_externos", "lg_solicitud_notas", "lg_solicitudes", "lg_eventos", "correos_enviados", "auditoria",
             "mensajes_soporte", "tickets_soporte")


def conteo(db: Session) -> dict:
    return {"despachos": db.scalar(select(func.count()).select_from(m.Organizacion)) or 0,
            "usuarios": db.scalar(select(func.count()).select_from(m.Usuario)) or 0,
            "clientes": db.scalar(select(func.count()).select_from(m.CrCliente)) or 0,
            "expedientes": db.scalar(select(func.count()).select_from(m.Expediente)) or 0,
            "solicitudes_contacto": db.scalar(select(func.count()).select_from(m.Base.metadata.tables["solicitudes"])) or 0}


def reiniciar(db: Session) -> dict:
    """Borra TODO lo de los despachos y la operación. No se puede deshacer."""
    antes = conteo(db)
    ids = [o.id for o in db.scalars(select(m.Organizacion)).all()]
    for oid in ids:
        eliminar_organizacion(db, db.get(m.Organizacion, oid))
        db.commit()
        borrar_archivos(oid)
    tablas = m.Base.metadata.tables
    for nombre in _GLOBALES:
        if nombre in tablas:
            db.execute(delete(tablas[nombre]))
    if "cm_cupones" in tablas and "usos" in tablas["cm_cupones"].c:  # los cupones se conservan, sin los usos de despachos borrados
        db.execute(tablas["cm_cupones"].update().values(usos=0))
    db.add(m.Auditoria(organizacion_id=None, usuario_id=None, usuario_email="Soporte Nomira (script)", accion="plataforma_reiniciada",
                       detalle={k: v for k, v in antes.items()}))
    db.commit()
    return {"antes": antes, "despues": conteo(db)}


def sembrar_piloto(db: Session, contrasena: str) -> dict:
    from ..services.academia import demo as academia_demo
    from ..services.afore import demo as afore_demo
    from ..services.agenda import demo as agenda_demo
    from ..services.bolsa import demo as bolsa_demo
    from ..services.clientes import demo as clientes_demo
    from ..services.escrituracion import demo as escrituracion_demo
    from ..services.evidencia import demo as evidencia_demo
    from ..services.leads import demo as leads_demo
    from ..services.liquidacion import demo as liquidacion_demo
    from ..services.rh import demo as rh_demo
    from .semilla import sembrar_demo

    if len(contrasena) < 8:
        raise ValueError("La contraseña del piloto debe tener al menos 8 caracteres.")
    r = sembrar_demo(db, email=PILOTO_EMAIL, contrasena=contrasena, nombre_org=PILOTO_DESPACHO, nombre_admin="Demo Nomira", equipo=False)
    e = PILOTO_EMAIL
    evidencia_demo.sembrar(db, e)
    evidencia_demo.sembrar_divorcio(db, e)
    afore_demo.sembrar(db, e)
    leads_demo.sembrar(db, e)
    academia_demo.sembrar(db, e)
    agenda_demo.sembrar(db, e)
    agenda_demo.sembrar_estrados(db, e)
    escrituracion_demo.sembrar(db, e)
    liquidacion_demo.sembrar(db, e)
    clientes_demo.sembrar(db, e)
    bolsa_demo.sembrar(db, e)
    rh_demo.sembrar(db, e)
    return r
