"""Datos de demostración de Nomira Leads (100 % ficticios). Se crean una sola vez."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from .. import modulos
from . import base


def sembrar(db: Session, email: str = "admin@demo.local") -> bool:
    admin = db.scalar(select(m.Usuario).where(m.Usuario.email == email))
    if not admin:
        return False
    oid = admin.organizacion_id
    if db.scalar(select(m.OrganizacionModulo.id).where(m.OrganizacionModulo.organizacion_id == oid, m.OrganizacionModulo.modulo == "leads")):
        return False
    modulos.fijar(db, oid, "leads", contratado=True, activo=True)
    analista = db.scalar(select(m.Usuario).where(m.Usuario.organizacion_id == oid, m.Usuario.rol == "analista")) or admin
    base.config(db, oid)
    et = {e.clave: e for e in base.etapas(db, oid, todas=True)}
    hoy, ahora = base.hoy(), m.ahora()
    fb = m.LdCampana(organizacion_id=oid, nombre="Facebook — despidos (noviembre)", canal="facebook", codigo=base.codigo(),
                     enlace_token=base.token_publico(), inversion=Decimal("3500.00"), inicio=hoy - timedelta(days=20), activa=True, creado_por_id=admin.id)
    mail = m.LdCampana(organizacion_id=oid, nombre="Boletín mensual por correo", canal="correo", codigo=base.codigo(),
                       enlace_token=base.token_publico(), activa=True, creado_por_id=admin.id)
    db.add_all([fb, mail])
    db.flush()

    def prospecto(nombre, tel, canal, etapa, materia, desc, campana=None, dias=1, resp=admin, respondido=True, **kw):
        p = m.LdProspecto(organizacion_id=oid, nombre=nombre, telefono=tel, canal=canal, campana_id=campana.id if campana else None,
                          etapa_id=et[etapa].id, materia=materia, descripcion=desc, responsable_id=resp.id, creado_por_id=admin.id,
                          entrada=kw.pop("entrada", "manual"), creado_en=ahora - timedelta(days=dias), ultima_actividad_en=ahora - timedelta(days=min(dias, 1)),
                          primera_respuesta_en=(ahora - timedelta(days=dias) + timedelta(hours=3)) if respondido else None, **kw)
        db.add(p)
        db.flush()
        base.actividad(db, p, "alta", "Prospecto registrado (demostración)", admin)
        base.consentir(db, p, ["whatsapp", "llamada"], "verbal", admin)
        return p

    def paso(p, tipo, dias, desc=None, hora=None, resp=admin):
        db.add(m.LdAccion(organizacion_id=oid, prospecto_id=p.id, tipo=tipo, fecha=hoy + timedelta(days=dias), hora=hora, descripcion=desc,
                          responsable_id=resp.id, creado_por_id=admin.id))

    a = prospecto("Ana Demo Martínez", "525500001001", "facebook", "nuevo", "Laboral", "La despidieron sin pagarle el finiquito.", fb, dias=0,
                  respondido=False, entrada="formulario")
    paso(a, "llamada", 0, "Primera llamada")
    b = prospecto("Bruno Ficticio Ruiz", "525500001002", "whatsapp", "contactado", "Familiar", "Quiere tramitar pensión alimenticia.", resp=analista)
    paso(b, "consulta", 2, "Consulta inicial en oficina", "11:00", resp=analista)
    db.add(m.LdMensaje(organizacion_id=oid, prospecto_id=b.id, canal="whatsapp", direccion="entrante", texto="¿Puedo llevar a mi hermana a la cita?",
                       estado="recibido", telefono=b.telefono, proveedor_id="demo.wamid.1", respondido=False))
    c = prospecto("Carla Ejemplo Soto", "525500001003", "correo", "propuesta_enviada", "AFORE y retiro", "Revisión de su retiro por desempleo.", mail, dias=6)
    paso(c, "seguimiento", -1, "Preguntar si revisó la propuesta")
    d = prospecto("Diego Prueba Luna", "525500001004", "referido", "consulta_realizada", "Civil", "Problema con contrato de arrendamiento.", dias=12)
    d.ultima_actividad_en = ahora - timedelta(days=10)
    e = prospecto("Elena Demo Vega", "525500001005", "facebook", "contratado", "Laboral", "Demanda por despido.", fb, dias=15,
                  contratado_en=ahora - timedelta(days=3), servicio_contratado="Demanda laboral", asunto_titulo="Demanda laboral — Elena Demo Vega")
    f = prospecto("Fernando Ficticio Paz", "525500001006", "google", "no_contratado", "Penal", "Asesoría penal.", dias=9,
                  motivo_perdida="Fuera de especialidad")
    for p in (e, f):
        base.actividad(db, p, "etapa", f"Etapa: … → {db.get(m.LdEtapa, p.etapa_id).nombre}", admin)
    db.commit()
    return True
