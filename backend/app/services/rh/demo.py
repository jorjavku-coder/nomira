"""Recursos humanos en la demo: el equipo del despacho y una empresa cliente, con avisos, solicitudes, documentos y una
quincena cerrada. Datos ficticios."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pymupdf
from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from .. import modulos
from . import base as rb


def _pdf(texto: str) -> bytes:
    d = pymupdf.open()
    d.new_page().insert_text((60, 80), texto + " (documento ficticio de demostración)", fontsize=11)
    return d.tobytes()


def sembrar(db: Session, email: str = "admin@demo.local") -> bool:
    admin = db.scalar(select(m.Usuario).where(m.Usuario.email == email))
    if not admin or db.scalar(select(m.RhEmpleado.id).where(m.RhEmpleado.organizacion_id == admin.organizacion_id).limit(1)):
        return False
    oid = admin.organizacion_id
    modulos.fijar(db, oid, "rh", contratado=True, activo=True)
    hoy = date.today()
    propia = rb.empresa_propia(db, db.get(m.Organizacion, oid))
    cliente = db.scalar(select(m.CrCliente).where(m.CrCliente.organizacion_id == oid, m.CrCliente.tipo == "moral"))
    ext = m.RhEmpresa(organizacion_id=oid, nombre=cliente.nombre if cliente else "Comercializadora Demo SA de CV", cliente_id=cliente.id if cliente else None,
                      rfc="CDE800101AB1", registro_patronal="Y1234567890", periodicidad="quincenal")
    db.add(ext)
    db.flush()
    gente = [(propia, "Laura Ejemplo Méndez", "Abogada asociada", "Litigio", 6 * 365 + 40, "1100"),
             (propia, "Diego Ficticio Ramos", "Pasante", "Litigio", 200, "420"),
             (propia, "Sofía Demo Castillo", "Recepción y administración", "Administración", 2 * 365 + 90, "520"),
             (ext, "Carlos Ejemplo Núñez", "Vendedor", "Ventas", 3 * 365 + 10, "600"),
             (ext, "María Ficticia Torres", "Almacenista", "Operación", 400, "480")]
    emps = []
    for emp, nombre, puesto, area, dias, sd in gente:
        e = m.RhEmpleado(organizacion_id=oid, empresa_id=emp.id, nombre=nombre, puesto=puesto, area=area, fecha_ingreso=hoy - timedelta(days=dias),
                         salario_diario=Decimal(sd), email=f"{nombre.split()[0].lower()}@ejemplo.test", telefono="5500000000")
        db.add(e)
        emps.append(e)
    db.flush()
    for e in emps[:3]:  # documentos base del equipo del despacho
        for tipo in ("ine", "curp", "csf", "contrato"):
            rel, nombre = rb.guardar_archivo(oid, e.id, f"{tipo}.pdf", _pdf(f"{rb.DOCUMENTOS[tipo]} de {e.nombre}"))
            db.add(m.RhDocumento(organizacion_id=oid, empleado_id=e.id, tipo=tipo, archivo=rel, nombre=nombre, tamano=1000))
    rel, nombre = rb.guardar_archivo(oid, emps[1].id, "domicilio.pdf", _pdf("Comprobante de domicilio"))
    db.add(m.RhDocumento(organizacion_id=oid, empleado_id=emps[1].id, tipo="domicilio", archivo=rel, nombre=nombre, tamano=1000, origen="portal",
                         estado="por_revisar"))
    lunes = hoy + timedelta(days=7 - hoy.weekday() + 7)
    db.add_all([
        m.RhIncidencia(organizacion_id=oid, empleado_id=emps[0].id, tipo="vacaciones", desde=lunes, hasta=lunes + timedelta(days=4), dias=Decimal(5),
                       motivo="Viaje familiar", estado="pendiente", origen="portal"),
        m.RhIncidencia(organizacion_id=oid, empleado_id=emps[2].id, tipo="permiso", desde=hoy + timedelta(days=3), hasta=hoy + timedelta(days=3), dias=Decimal(1),
                       motivo="Trámite personal", estado="pendiente", origen="portal"),
        m.RhIncidencia(organizacion_id=oid, empleado_id=emps[3].id, tipo="falta", desde=hoy - timedelta(days=9), hasta=hoy - timedelta(days=9), dias=Decimal(1),
                       estado="aprobada", origen="rh", resuelta_por_id=admin.id)])
    db.add_all([
        m.RhAviso(organizacion_id=oid, titulo="Pago de aguinaldo", cuerpo="El aguinaldo se depositará a más tardar el 19 de diciembre. Revisen que su cuenta esté al día.",
                  fijado=True, requiere_acuse=True, creado_por_id=admin.id),
        m.RhAviso(organizacion_id=oid, empresa_id=propia.id, titulo="Junta de equipo el viernes",
                  cuerpo="Junta general el viernes a las 9:00 en la sala de juntas para revisar la agenda de audiencias del mes.", creado_por_id=admin.id)])
    db.flush()
    # quincena anterior cerrada de la empresa cliente
    fin = hoy.replace(day=15) if hoy.day > 15 else (hoy.replace(day=1) - timedelta(days=1))
    inicio = fin.replace(day=1) if fin.day == 15 else fin.replace(day=16)
    p = m.RhPeriodo(organizacion_id=oid, empresa_id=ext.id, inicio=inicio, fin=fin, fecha_pago=fin, estado="cerrado")
    db.add(p)
    db.flush()
    for e in emps[3:]:
        r = rb.armar_recibo(db, p, e)
        ded = [{"concepto": "ISR retenido (dato del contador)", "importe": "350.00"}, {"concepto": "Cuota obrera IMSS (dato del contador)", "importe": "180.00"}]
        db.add(m.RhRecibo(organizacion_id=oid, periodo_id=p.id, empleado_id=e.id, dias_pagados=r["dias_pagados"], faltas=r["faltas"],
                          percepciones=r["percepciones"], deducciones=ded, neto=rb.neto(r["percepciones"], ded)))
    db.commit()
    return True
