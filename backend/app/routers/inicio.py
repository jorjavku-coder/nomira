"""Inicio: lo que el abogado necesita ver al entrar, en una sola consulta y solo de los módulos que tiene activos.

Números que se pueden presionar, lo de hoy en la agenda y el avance de los primeros pasos. No devuelve datos de
expedientes más allá del título del asunto y del pendiente (lo mismo que muestra la Agenda al mismo usuario).
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import usuario_actual
from ..services import modulos
from ..services.agenda import base as ag
from ..services.clientes import base as cb

router = APIRouter(prefix="/api/inicio", tags=["Inicio"])


def _contar(db: Session, modelo, *condiciones) -> int:
    return db.scalar(select(func.count()).select_from(modelo).where(*condiciones)) or 0


@router.get("")
def inicio(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    oid = u.organizacion_id
    activos = set(modulos.activos(db, oid))
    numeros: list[dict] = []
    hoy_lista: list[dict] = []
    aviso = None

    if "agenda" in activos:
        ref = ag.hoy()
        pend = db.scalars(select(m.AgEvento).where(m.AgEvento.organizacion_id == oid, m.AgEvento.estado == "pendiente",
                                                   m.AgEvento.fecha <= ref + timedelta(days=7))
                          .order_by(m.AgEvento.fecha, m.AgEvento.hora.nullsfirst()).limit(50)).all()
        vencidos = [e for e in pend if e.fecha < ref]
        de_hoy = [e for e in pend if e.fecha == ref]
        if vencidos or de_hoy:
            n = len(vencidos) + len(de_hoy)
            aviso = {"texto": f"{n} {'pendiente vencido o de hoy' if n == 1 else 'pendientes vencidos o de hoy'}", "href": "/agenda"}
        numeros.append({"clave": "agenda", "etiqueta": "Hoy en agenda", "valor": str(len(de_hoy)), "href": "/agenda"})
        asuntos = {a.id: a.titulo for a in db.scalars(select(m.AgAsunto).where(m.AgAsunto.id.in_({e.asunto_id for e in pend if e.asunto_id})))}
        for e in pend[:5]:
            hoy_lista.append({"id": e.id, "titulo": e.titulo, "fecha": e.fecha.isoformat(), "hora": e.hora, "tipo": e.tipo,
                              "situacion": "vencido" if e.fecha < ref else "hoy" if e.fecha == ref else "proximo",
                              "asunto": asuntos.get(e.asunto_id), "href": f"/agenda/eventos/{e.id}"})

    cuentas = cb.cuentas_org(db, oid, ag.hoy())
    por_cobrar = sum((max(c.saldo, cb.CERO) for c in cuentas.values()), cb.CERO)
    if cuentas:
        numeros.append({"clave": "cobranza", "etiqueta": "Por cobrar", "valor": f"${por_cobrar:,.2f}", "href": "/clientes?filtro=con_saldo",
                        "dinero": True})

    if "leads" in activos:
        from .leads import _seleccion  # misma regla que la bandeja de Prospectos (nuevos + por responder)
        n = len(_seleccion(db, u, "nuevos")) + len(_seleccion(db, u, "responder"))
        numeros.append({"clave": "leads", "etiqueta": "Prospectos sin contestar", "valor": str(n), "href": "/leads"})

    if "rh" in activos:
        n = _contar(db, m.RhIncidencia, m.RhIncidencia.organizacion_id == oid, m.RhIncidencia.estado == "pendiente")
        numeros.append({"clave": "rh", "etiqueta": "Solicitudes de RH", "valor": str(n), "href": "/rh?tab=solicitudes"})

    org = db.get(m.Organizacion, oid)
    pasos = {
        "despacho": bool(org and org.logo_actualizado),
        "equipo": _contar(db, m.Usuario, m.Usuario.organizacion_id == oid, m.Usuario.eliminado_en.is_(None)) > 1,
        "cliente": _contar(db, m.CrCliente, m.CrCliente.organizacion_id == oid) > 0,
        "agenda": _contar(db, m.AgEvento, m.AgEvento.organizacion_id == oid) > 0,
        "asistente": _contar(db, m.AsSolicitud, m.AsSolicitud.organizacion_id == oid) > 0,
    }
    return {"modulos": sorted(activos), "aviso": aviso, "numeros": numeros[:4], "hoy": hoy_lista, "pasos": pasos}
