"""Liquidaciones de demostración (datos ficticios): dos cálculos ligados al asunto laboral de la Agenda demo. Una sola vez."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from ..agenda.base import hoy
from . import motor


def sembrar(db: Session, email: str = "admin@demo.local") -> bool:
    admin = db.scalar(select(m.Usuario).where(m.Usuario.email == email))
    if not admin:
        return False
    oid = admin.organizacion_id
    if db.scalar(select(m.LqCalculo.id).where(m.LqCalculo.organizacion_id == oid)):
        return False
    asunto = db.scalar(select(m.AgAsunto).where(m.AgAsunto.organizacion_id == oid, m.AgAsunto.materia == "laboral").order_by(m.AgAsunto.id))
    h = hoy()
    baja = h - timedelta(days=120)
    casos = [
        ("Pedro Ruiz Ficticio", {"fecha_ingreso": (baja - timedelta(days=365 * 6 + 40)).isoformat(), "fecha_baja": baja.isoformat(),
                                 "causa": "despido_injustificado", "salario_diario": "650.00", "dias_pendientes_pago": "6",
                                 "horas_extra": [{"desde": (baja - timedelta(days=90)).isoformat(), "hasta": baja.isoformat(), "horas_semana": "56"}]},
         Decimal("0.6")),
        ("Laura Ruiz Ficticia", {"fecha_ingreso": (baja - timedelta(days=365 * 2 + 100)).isoformat(), "fecha_baja": baja.isoformat(),
                                  "causa": "despido_injustificado", "salario_diario": "420.00"}, None),
    ]
    for nombre, datos, prop in casos:
        d = motor.Datos(**{**datos, "fecha_ingreso": motor.date.fromisoformat(datos["fecha_ingreso"]), "fecha_baja": motor.date.fromisoformat(datos["fecha_baja"]),
                           "salario_diario": Decimal(datos["salario_diario"]), "dias_pendientes_pago": Decimal(datos.get("dias_pendientes_pago", "0")),
                           "horas_extra": [motor.PeriodoExtra(motor.date.fromisoformat(p["desde"]), motor.date.fromisoformat(p["hasta"]), Decimal(p["horas_semana"]))
                                           for p in datos.get("horas_extra", [])]})
        r = motor.calcular(d, h)
        total = Decimal(r["total"])
        db.add(m.LqCalculo(organizacion_id=oid, titulo=f"{r['causa_nombre']} — {nombre}", trabajador=nombre, patron="Comercializadora Demo, S.A. de C.V.",
                           ag_asunto_id=asunto.id if asunto else None, causa=datos["causa"], datos=datos, resultado=r, total=total,
                           propuesta=(total * prop).quantize(Decimal("0.01")) if prop else None,
                           autorizado=(total * Decimal("0.75")).quantize(Decimal("0.01")) if prop else None,
                           notas="Cálculo de demostración: datos ficticios.", creado_por_id=admin.id))
    db.commit()
    return True
