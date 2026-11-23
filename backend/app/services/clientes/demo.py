"""Clientes de demostración (ficticios): directorio, vínculos con asuntos de ejemplo, honorarios y pagos. Una sola vez."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from ..agenda.base import hoy
from . import base as cb


def sembrar(db: Session, email: str = "admin@demo.local") -> bool:
    admin = db.scalar(select(m.Usuario).where(m.Usuario.email == email))
    if not admin or db.scalar(select(m.CrCliente.id).where(m.CrCliente.organizacion_id == admin.organizacion_id).limit(1)):
        return False
    oid, h = admin.organizacion_id, hoy()

    def cliente(**kw) -> m.CrCliente:
        c = m.CrCliente(organizacion_id=oid, responsable_id=admin.id, creado_por_id=admin.id, origen="manual", **kw)
        db.add(c)
        db.flush()
        return c

    juan = cliente(nombre="Juan Demo Ficticio", email="juan.demo@ejemplo.test", telefono="5500000001", etiquetas=["Laboral"],
                   domicilio="Calle Ficticia 123, Col. Demo, Toluca, Estado de México", codigo_postal="50000",
                   notas="Cliente de demostración: datos ficticios.")
    laura = cliente(nombre="Laura Ficticia Ramírez", email="laura.demo@ejemplo.test", telefono="5500000002", etiquetas=["Familiar"])
    empresa = cliente(tipo="moral", nombre="Comercializadora Demo SA de CV", rfc="CDE200101AB1", email="contacto@comercializadora.test",
                      contacto="Lic. Ana Ejemplo", etiquetas=["Iguala", "Empresa"], regimen_fiscal="General de Ley Personas Morales")
    # vínculos con lo que ya existe en la demo
    for x in db.scalars(select(m.EvAsunto).where(m.EvAsunto.organizacion_id == oid)):
        if cb.plano(x.cliente) == cb.plano(juan.nombre):
            x.cr_cliente_id = juan.id
        elif cb.plano(x.cliente) == cb.plano(laura.nombre):
            x.cr_cliente_id = laura.id
    for a in db.scalars(select(m.AgAsunto).where(m.AgAsunto.organizacion_id == oid)):
        if "Comercializadora" in a.titulo:
            a.cr_cliente_id = juan.id
    # honorarios y pagos
    def cargo(c, concepto, monto, vence, grupo=None):
        g = m.CrCargo(organizacion_id=oid, cliente_id=c.id, concepto=concepto, monto=Decimal(monto), fecha=h - timedelta(days=40),
                      vence=vence, grupo=grupo, creado_por_id=admin.id)
        db.add(g)
        db.flush()
        return g

    def pago(c, monto, dias, metodo="transferencia", g=None):
        db.add(m.CrPago(organizacion_id=oid, cliente_id=c.id, cargo_id=g.id if g else None, folio=cb.siguiente_folio(db, oid), monto=Decimal(monto),
                        fecha=h - timedelta(days=dias), metodo=metodo, referencia="Demo", registrado_por_id=admin.id))
        db.flush()

    a1 = cargo(juan, "Honorarios: demanda laboral (anticipo)", "8000", h - timedelta(days=30))
    cargo(juan, "Honorarios: demanda laboral (segundo pago)", "7000", h - timedelta(days=3))
    pago(juan, "8000", 28, g=a1)
    cargo(laura, "Honorarios: divorcio voluntario", "12000", h + timedelta(days=15))
    pago(laura, "4000", 10, "efectivo")
    for i in range(3):
        g = cargo(empresa, f"Iguala mensual ({i + 1}/3)", "6500", cb.sumar_meses(h.replace(day=1), i - 1), grupo="demo-iguala")
        if i == 0:
            pago(empresa, "6500", 20, g=g)
    db.commit()
    return True
