"""Datos de demostración de Nomira Academia (ficticios). Se crean una sola vez."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from .. import modulos
from . import nomira


def sembrar(db: Session, email: str = "admin@demo.local") -> bool:
    admin = db.scalar(select(m.Usuario).where(m.Usuario.email == email))
    if not admin:
        return False
    oid = admin.organizacion_id
    if db.scalar(select(m.OrganizacionModulo.id).where(m.OrganizacionModulo.organizacion_id == oid, m.OrganizacionModulo.modulo == "academia")):
        return False
    modulos.fijar(db, oid, "academia", contratado=True, activo=True)
    nomira.asegurar(db)
    analista = db.scalar(select(m.Usuario).where(m.Usuario.organizacion_id == oid, m.Usuario.rol == "analista"))
    c = m.AcCurso(organizacion_id=oid, titulo="Alta ordenada de casos AFORE en el despacho", materia="AFORE", roles=["Abogados", "Asistentes"],
                  instructor=admin.nombre, descripcion="Proceso interno del despacho para registrar un caso AFORE: datos mínimos, checklist y "
                  "primer seguimiento. Material de ejemplo.", duracion_min=15, modalidad="combinado", estado="publicado", juridico=False,
                  publicado_por_id=admin.id, publicado_en=m.ahora(), creado_por_id=admin.id, calificacion_minima=None)
    db.add(c)
    db.flush()
    mod = m.AcModulo(curso_id=c.id, titulo="Proceso del despacho", orden=0)
    db.add(mod)
    db.flush()
    db.add_all([
        m.AcLeccion(curso_id=c.id, modulo_id=mod.id, orden=0, titulo="Datos mínimos para abrir el caso", duracion_min=5,
                    texto="Registre quién se comunica, su relación con el titular, el tipo de problema y cómo prefiere que le contacten. "
                          "Lo que no se sepa se marca como «Pendiente de confirmar»."),
        m.AcLeccion(curso_id=c.id, modulo_id=mod.id, orden=1, titulo="Checklist y primer seguimiento", duracion_min=5,
                    texto="Revise el checklist sugerido, pida al cliente los documentos que falten por el portal y defina la siguiente actividad "
                          "con responsable y fecha.",
                    actividad={"pregunta": "¿Qué debe tener todo caso abierto?", "opciones": ["Un monto estimado", "Una siguiente actividad con responsable y fecha"],
                               "correcta": 1, "explicacion": "Así ningún caso queda detenido sin que nadie lo note."}),
    ])
    db.add(m.AcSesion(organizacion_id=oid, curso_id=c.id, titulo="Sesión de dudas (ejemplo)", inicio=m.ahora() + timedelta(days=3), duracion_min=45,
                      notas="El enlace de la reunión lo comparte el instructor.", creado_por_id=admin.id))
    equipo = m.AcEquipo(organizacion_id=oid, nombre="Atención a clientes")
    db.add(equipo)
    db.flush()
    for u in filter(None, (admin, analista)):
        db.add(m.AcEquipoMiembro(equipo_id=equipo.id, usuario_id=u.id))
    atencion = db.scalar(select(m.AcCurso).where(m.AcCurso.clave == "nomira-atencion-inicial"))
    if atencion:
        db.add(m.AcAsignacion(organizacion_id=oid, curso_id=atencion.id, equipo_id=equipo.id, tipo="obligatorio",
                              fecha_sugerida=date.today() + timedelta(days=10), asignado_por_id=admin.id))
    db.add(m.AcAsignacion(organizacion_id=oid, curso_id=c.id, equipo_id=equipo.id, tipo="recomendado", asignado_por_id=admin.id))
    db.commit()
    return True
