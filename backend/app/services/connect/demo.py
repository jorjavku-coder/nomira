"""Nomira Connect en la demo: el juicio laboral de Juan Demo Ficticio publicado en su portal, con etapas avanzadas,
un mensaje del abogado y una pregunta del cliente. Datos ficticios."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from .. import modulos
from ..agenda.base import hoy
from . import base as cb
from . import plantillas as pl


def sembrar(db: Session, email: str = "admin@demo.local") -> bool:
    admin = db.scalar(select(m.Usuario).where(m.Usuario.email == email))
    if not admin or db.scalar(select(m.CnSeguimiento.id).where(m.CnSeguimiento.organizacion_id == admin.organizacion_id).limit(1)):
        return False
    oid = admin.organizacion_id
    modulos.fijar(db, oid, "connect", contratado=True, activo=True)
    a = db.scalar(select(m.AgAsunto).where(m.AgAsunto.organizacion_id == oid, m.AgAsunto.cr_cliente_id.is_not(None)).order_by(m.AgAsunto.id))
    if not a:
        db.commit()
        return False
    s = cb.crear(db, a, pl.BASE["laboral"]["nombre"], "laboral", pl.BASE["laboral"]["etapas"], admin)
    s.creado_en = m.ahora() - timedelta(days=75)
    etapas = cb.etapas_de(db, s)
    for i, e in enumerate(etapas[:5]):
        e.estado, e.fecha = "completada", hoy() - timedelta(days=70 - i * 14)
    etapas[2].estado, etapas[2].fecha = "omitida", None  # sin conciliación en este asunto
    etapas[4].nota_publica = "Presentamos su demanda ante el Tribunal Laboral."
    act = etapas[5]
    act.estado, act.fecha = "actual", hoy() - timedelta(days=12)
    act.nota_publica = "La audiencia preliminar está programada. Le confirmaremos si necesita asistir."
    act.nota_interna = "Preparar interrogatorio y revisar pruebas de la contraparte (nota interna de demostración)."
    s.visible_cliente, s.mostrar_audiencias = True, True
    s.ultimo_movimiento_fecha, s.ultimo_movimiento_texto = hoy() - timedelta(days=12), "El tribunal fijó fecha para la audiencia preliminar."
    s.ultima_revision_en, s.ultima_revision_por_id = m.ahora() - timedelta(days=2), admin.id
    s.mensaje_publico = "Todo va en orden. Le avisaremos en cuanto haya una novedad."
    cb.evento(db, s, "etapa", "Etapa completada: Presentación de la demanda", "Presentamos su demanda ante el Tribunal Laboral.", True, admin)
    cb.evento(db, s, "etapa", f"Nueva etapa: {act.nombre}", act.nota_publica, True, admin)
    cb.evento(db, s, "revision", "Su abogado revisó el expediente", None, True, admin)
    db.add(m.CnMensaje(organizacion_id=oid, cliente_id=a.cr_cliente_id, asunto_id=a.id, autor="cliente", motivo="seguimiento",
                       texto="Buenas tardes, ¿ya hay fecha para la audiencia? (mensaje de demostración)", estado="nuevo",
                       creado_en=m.ahora() - timedelta(hours=3)))
    db.commit()
    return True
