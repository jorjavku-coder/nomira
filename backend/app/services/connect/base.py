"""Reglas de Nomira Connect: crear el seguimiento de un asunto, moverlo de etapa y armar lo que ve el cliente.

Lo que ve el cliente se arma SOLO desde campos públicos (nombre, explicación, nota_publica, eventos visibles).
La nota interna de cada etapa y las notas del asunto nunca se incluyen en `publico()`.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from ..agenda.base import hoy
from . import plantillas as pl

ESTADOS_PANEL = set(pl.ESTADOS)


def etapas_de(db: Session, s: m.CnSeguimiento) -> list[m.CnEtapa]:
    return list(db.scalars(select(m.CnEtapa).where(m.CnEtapa.seguimiento_id == s.id).order_by(m.CnEtapa.orden, m.CnEtapa.id)))


def evento(db: Session, s: m.CnSeguimiento, tipo: str, titulo: str, detalle: str | None = None, visible: bool = True,
           u: m.Usuario | None = None) -> m.CnEvento:
    e = m.CnEvento(organizacion_id=s.organizacion_id, seguimiento_id=s.id, tipo=tipo, titulo=titulo[:200],
                   detalle=(detalle or None) and detalle[:1000], visible_cliente=visible, usuario_id=u.id if u else None)
    db.add(e)
    if visible:
        s.publico_actualizado_en = m.ahora()
    return e


def crear(db: Session, asunto: m.AgAsunto, nombre: str | None, especialidad: str | None, etapas: list[dict], u: m.Usuario) -> m.CnSeguimiento:
    s = m.CnSeguimiento(organizacion_id=asunto.organizacion_id, asunto_id=asunto.id, plantilla_nombre=nombre, especialidad=especialidad,
                        estado="activo", visible_cliente=False, mostrar_audiencias=True, mostrar_pagos=False, creado_por_id=u.id)
    db.add(s)
    db.flush()
    for i, e in enumerate(pl.limpiar_etapas(etapas)):
        db.add(m.CnEtapa(organizacion_id=s.organizacion_id, seguimiento_id=s.id, orden=i, nombre=e["nombre"], explicacion=e["explicacion"],
                         opcional=e["opcional"], estado="actual" if i == 0 else "pendiente", fecha=hoy() if i == 0 else None))
    db.flush()
    evento(db, s, "inicio", "Iniciamos el seguimiento de su asunto", None, True, u)
    return s


def marcar_actual(db: Session, s: m.CnSeguimiento, destino: m.CnEtapa, u: m.Usuario) -> str | None:
    """Pone `destino` como etapa actual. Las anteriores quedan completadas (salvo las omitidas) y las
    posteriores vuelven a «próxima»: así también se puede regresar a una etapa anterior."""
    anterior = None
    for e in etapas_de(db, s):
        if e.estado == "actual" and e.id != destino.id:
            anterior = e.nombre
        if e.id == destino.id:
            continue
        antes = (e.orden, e.id) < (destino.orden, destino.id)
        if antes and e.estado not in ("completada", "omitida"):
            e.estado, e.fecha = "completada", e.fecha if e.estado == "completada" else (e.fecha or hoy())
        elif not antes and e.estado in ("actual", "completada", "atencion", "incidencia", "suspendida"):
            e.estado, e.fecha = "pendiente", None
        e.actualizado_por_id, e.actualizado_en = u.id, m.ahora()
    destino.estado, destino.fecha = "actual", hoy()
    destino.actualizado_por_id, destino.actualizado_en = u.id, m.ahora()
    return anterior


def _etapa_publica(e: m.CnEtapa) -> dict:
    return {"id": e.id, "nombre": e.nombre, "explicacion": e.explicacion, "opcional": e.opcional, "estado": e.estado,
            "estado_texto": pl.ESTADOS.get(e.estado, e.estado), "fecha": e.fecha.isoformat() if e.fecha else None, "nota": e.nota_publica}


def publico(db: Session, s: m.CnSeguimiento, a: m.AgAsunto) -> dict:
    """Lo que ve el cliente. NO incluye notas internas, notas del asunto ni eventos privados."""
    etapas = [e for e in etapas_de(db, s) if e.estado != "omitida"]
    actual = next((e for e in etapas if e.estado in ("actual", "atencion", "incidencia", "suspendida")), None)
    resp = db.get(m.Usuario, a.responsable_id) if a.responsable_id else None
    eventos = db.scalars(select(m.CnEvento).where(m.CnEvento.seguimiento_id == s.id, m.CnEvento.visible_cliente.is_(True))
                         .order_by(m.CnEvento.creado_en.desc(), m.CnEvento.id.desc()).limit(30)).all()
    audiencias = []
    if s.mostrar_audiencias:
        for ev in db.scalars(select(m.AgEvento).where(m.AgEvento.asunto_id == a.id, m.AgEvento.tipo == "audiencia",
                                                     m.AgEvento.estado == "pendiente", m.AgEvento.fecha >= hoy())
                             .order_by(m.AgEvento.fecha, m.AgEvento.hora).limit(5)):
            audiencias.append({"titulo": ev.titulo, "fecha": ev.fecha.isoformat(), "hora": ev.hora, "lugar": ev.lugar})
    return {
        "id": s.id, "asunto": a.titulo, "numero": a.numero, "tribunal": a.tribunal, "abogado": resp.nombre if resp else None,
        "especialidad": pl.ESPECIALIDADES.get(s.especialidad or "", s.plantilla_nombre), "estado": s.estado,
        "inicio": s.creado_en.date().isoformat(), "etapa_actual": _etapa_publica(actual) if actual else None,
        "etapas": [_etapa_publica(e) for e in etapas],
        "ultimo_movimiento": {"fecha": s.ultimo_movimiento_fecha.isoformat(), "texto": s.ultimo_movimiento_texto} if s.ultimo_movimiento_fecha else None,
        "ultima_revision": s.ultima_revision_en.isoformat() if s.ultima_revision_en else None,
        "actualizado_en": s.publico_actualizado_en.isoformat() if s.publico_actualizado_en else None,
        "mensaje": s.mensaje_publico, "accion_cliente": s.accion_cliente,
        "audiencias": audiencias,
        "historial": [{"titulo": e.titulo, "detalle": e.detalle, "fecha": e.creado_en.isoformat(), "tipo": e.tipo} for e in eventos],
    }


def panel(db: Session, s: m.CnSeguimiento, a: m.AgAsunto) -> dict:
    """Vista del despacho: lo público más las notas internas y el historial completo."""
    d = publico(db, s, a)
    nombres = {x.id: x.nombre for x in db.scalars(select(m.Usuario).where(m.Usuario.organizacion_id == s.organizacion_id))}
    d["etapas"] = [{**_etapa_publica(e), "nota_interna": e.nota_interna, "actualizado_por": nombres.get(e.actualizado_por_id),
                    "actualizado_en": e.actualizado_en.isoformat() if e.actualizado_en else None} for e in etapas_de(db, s)]
    d["historial"] = [{"titulo": e.titulo, "detalle": e.detalle, "fecha": e.creado_en.isoformat(), "tipo": e.tipo, "visible": e.visible_cliente,
                       "por": nombres.get(e.usuario_id)}
                      for e in db.scalars(select(m.CnEvento).where(m.CnEvento.seguimiento_id == s.id)
                                          .order_by(m.CnEvento.creado_en.desc(), m.CnEvento.id.desc()).limit(100))]
    cli = db.get(m.CrCliente, a.cr_cliente_id) if a.cr_cliente_id else None
    d.update({"asunto_id": a.id, "visible_cliente": s.visible_cliente, "mostrar_audiencias": s.mostrar_audiencias, "mostrar_pagos": s.mostrar_pagos,
              "cliente": {"id": cli.id, "nombre": cli.nombre, "email": bool(cli.email), "telefono": bool(cli.telefono)} if cli else None,
              "plantilla": s.plantilla_nombre, "ultimo_movimiento_fecha": s.ultimo_movimiento_fecha.isoformat() if s.ultimo_movimiento_fecha else None,
              "ultimo_movimiento_texto": s.ultimo_movimiento_texto,
              "ultima_revision_por": nombres.get(s.ultima_revision_por_id)})
    return d


def dias_sin_actualizar(s: m.CnSeguimiento) -> int | None:
    ref = s.publico_actualizado_en or s.creado_en
    return (m.ahora() - (ref if ref.tzinfo else ref.replace(tzinfo=m.ahora().tzinfo))).days if ref else None

