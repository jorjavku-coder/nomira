"""Calendario privado de cada persona para Google Calendar u Outlook (sin sesión: lo valida el enlace).
Solo incluye lo que le toca a esa persona y respeta su opción de detalle («reservado» por omisión)."""
from __future__ import annotations

import hashlib
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import ip_cliente
from ..freno import Ventana
from ..services import modulos
from ..services.agenda import base
from .agenda import ics

router = APIRouter(prefix="/api/agenda-feed", tags=["Nomira Agenda Jurídica — calendario externo"])
_freno = Ventana(60, 600)


@router.get("/{token}.ics")
def feed(token: str, request: Request, db: Session = Depends(get_db)):
    ip = ip_cliente(request) or "?"
    if _freno.excedida(ip):
        raise HTTPException(429, "Demasiadas consultas.")
    _freno.registrar(ip)
    if len(token) > 100:
        raise HTTPException(404, "No encontrado.")
    p = db.scalar(select(m.AgPreferencia).where(m.AgPreferencia.feed_token_hash == hashlib.sha256(token.encode()).hexdigest()))
    u = db.get(m.Usuario, p.usuario_id) if p else None
    org = db.get(m.Organizacion, u.organizacion_id) if u else None
    if not u or not u.activo or u.eliminado_en or not org or org.estado != "activa" or "agenda" not in modulos.activos(db, org.id):
        raise HTTPException(404, "No encontrado.")
    ref = base.hoy()
    filas = [e for e in db.scalars(select(m.AgEvento).where(m.AgEvento.organizacion_id == org.id, m.AgEvento.estado == "pendiente",
                                                            m.AgEvento.fecha >= ref - timedelta(days=30), m.AgEvento.fecha <= ref + timedelta(days=365)))
             if u.id in base.involucrados(e)]
    return Response(ics(filas, db, p.feed_detalle), media_type="text/calendar; charset=utf-8", headers={"Cache-Control": "no-store"})
