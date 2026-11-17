"""Soporte desde la app del cliente: cualquier usuario de la organización escribe a Nomira y ve
las respuestas. Cada organización solo ve sus propias conversaciones."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import auditar, usuario_actual
from .plataforma import Mensaje, t_detalle, t_resumen

router = APIRouter(prefix="/api/soporte", tags=["soporte"])


class TicketNuevo(BaseModel):
    asunto: str = Field(min_length=2, max_length=200)
    texto: str = Field(min_length=1, max_length=5000)


def _mio(db: Session, tid: int, u: m.Usuario) -> m.TicketSoporte:
    t = db.get(m.TicketSoporte, tid)
    if not t or t.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrado.")
    return t


@router.get("")
def listar(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    ts = db.scalars(select(m.TicketSoporte).where(m.TicketSoporte.organizacion_id == u.organizacion_id)
                    .order_by(m.TicketSoporte.actualizado_en.desc())).all()
    return [t_resumen(t) for t in ts]


@router.get("/sin-leer")
def sin_leer(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return {"total": db.scalar(select(func.count()).select_from(m.TicketSoporte).where(
        m.TicketSoporte.organizacion_id == u.organizacion_id, m.TicketSoporte.leido_cliente.is_(False)))}


@router.post("", status_code=201)
def crear(d: TicketNuevo, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    t = m.TicketSoporte(organizacion_id=u.organizacion_id, asunto=d.asunto.strip(), creado_por_id=u.id,
                        leido_cliente=True, leido_plataforma=False)
    t.mensajes.append(m.MensajeSoporte(autor_tipo="cliente", autor_nombre=u.nombre, usuario_id=u.id, texto=d.texto.strip()))
    db.add(t)
    db.flush()
    auditar(db, u, "soporte_solicitado", "ticket", t.id, request=request)
    db.commit()
    return t_detalle(t)


@router.get("/{tid}")
def ver(tid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    t = _mio(db, tid, u)
    if not t.leido_cliente:
        t.leido_cliente = True
        db.commit()
    return t_detalle(t)


@router.post("/{tid}/mensajes", status_code=201)
def responder(tid: int, d: Mensaje, request: Request, u: m.Usuario = Depends(usuario_actual),
              db: Session = Depends(get_db)):
    t = _mio(db, tid, u)
    t.mensajes.append(m.MensajeSoporte(autor_tipo="cliente", autor_nombre=u.nombre, usuario_id=u.id, texto=d.texto.strip()))
    t.estado, t.leido_plataforma, t.leido_cliente, t.actualizado_en = "abierto", False, True, m.ahora()
    auditar(db, u, "soporte_respondido", "ticket", t.id, request=request)
    db.commit()
    return t_detalle(t)


@router.patch("/{tid}")
def cerrar(tid: int, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """El cliente marca su consulta como resuelta (se reabre sola si alguien vuelve a escribir)."""
    t = _mio(db, tid, u)
    t.estado = "cerrado"
    auditar(db, u, "soporte_cerrado", "ticket", t.id, request=request)
    db.commit()
    return t_detalle(t)
