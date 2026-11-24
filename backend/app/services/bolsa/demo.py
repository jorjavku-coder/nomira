"""Bolsa de trabajo en la demo: una vacante publicada solo en la página del despacho (no en el portal público),
dos candidatos ficticios y una prueba contestada. Activa «Pruebas psicométricas» para mostrar la versión premium."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from .. import modulos
from . import base as bt, pruebas as pb


def sembrar(db: Session, email: str = "admin@demo.local") -> bool:
    admin = db.scalar(select(m.Usuario).where(m.Usuario.email == email))
    if not admin or db.scalar(select(m.BtVacante.id).where(m.BtVacante.organizacion_id == admin.organizacion_id).limit(1)):
        return False
    oid = admin.organizacion_id
    modulos.fijar(db, oid, "psicometria", contratado=True, activo=True)
    p = bt.perfil(db, db.get(m.Organizacion, oid))
    p.nombre_publico, p.ciudad = "Despacho Demostración (datos ficticios)", "Ciudad de México"
    p.descripcion = "Página de ejemplo. Los datos son ficticios."
    ahora = datetime.now(timezone.utc)
    v = m.BtVacante(organizacion_id=oid, codigo=bt.codigo(), titulo="Abogado(a) litigante laboral (ejemplo)", area="laboral", puesto="abogado",
                    jornada="completa", modalidad="hibrido", estado_republica="Ciudad de México", ciudad="Benito Juárez",
                    sueldo_min=Decimal("18000"), sueldo_max=Decimal("25000"), en_portal=False, estado="publicada", publicada_en=ahora - timedelta(days=6),
                    descripcion="Llevar juicios laborales de la parte trabajadora: conciliación prejudicial, demandas, audiencias y seguimiento con clientes.",
                    requisitos="Título y cédula profesional. Dos años de experiencia en litigio laboral.", ofrecemos="Prestaciones de ley, horario híbrido y capacitación.",
                    pruebas=["laboral", "big5"], creado_por_id=admin.id)
    db.add(v)
    db.flush()
    c1 = m.BtCandidato(organizacion_id=oid, vacante_id=v.id, nombre="Mariana Ejemplo Torres", email="mariana@ejemplo.test", telefono="5500000001",
                       ciudad="Coyoacán, CDMX", cedula="12345678", experiencia="3-5", etapa="entrevista", calificacion=4,
                       mensaje="Me interesa porque llevo juicios laborales desde hace tres años.", creado_en=ahora - timedelta(days=4))
    c2 = m.BtCandidato(organizacion_id=oid, vacante_id=v.id, nombre="Jorge Ficticio Ramos", email="jorge@ejemplo.test", telefono="5500000002",
                       ciudad="Naucalpan, Edo. Méx.", experiencia="1-3", creado_en=ahora - timedelta(days=1))
    db.add_all([c1, c2])
    db.flush()
    resp = [q["correcta"] for q in pb.LABORAL]
    resp[3] = 0  # un error
    a, _ = bt.nueva_aplicacion(db, c1, "laboral", pb.PRUEBAS["laboral"]["nombre"], admin.id)
    a.estado, a.iniciada_en, a.consentimiento_en, a.terminada_en = "terminada", ahora - timedelta(days=2, minutes=9), ahora - timedelta(days=2, minutes=9), ahora - timedelta(days=2)
    a.respuestas, a.resultado = {"respuestas": resp}, {**pb.calificar(pb.PRUEBAS["laboral"], resp), "minutos_usados": 9.0, "fuera_de_tiempo": False}
    db.commit()
    return True
