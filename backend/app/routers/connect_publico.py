"""Portal del cliente de Nomira Connect (/api/mi-portal/*).

El cliente entra con el enlace que le dio su despacho (token en X-Enlace) y, si tiene correo, con un código.
Ve SOLO: los asuntos donde él es el cliente y cuyo seguimiento el despacho publicó, con sus campos públicos;
sus pagos pendientes si el despacho lo autorizó; y sus mensajes con el despacho. Nunca notas internas ni
asuntos de otros clientes u otros despachos.
"""
from __future__ import annotations

import hmac
from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, ip_cliente
from ..freno import Ventana
from ..services import envios, modulos, plantillas_correo
from ..services.agenda.base import hoy
from ..services.clientes import base as cl
from ..services.connect import base as cb
from ..services.connect import portal
from ..services.evidencia import solicitudes as sol
from .connect import MOTIVOS

router = APIRouter(prefix="/api/mi-portal", tags=["Nomira Connect — portal del cliente"])
_fallos_ip = Ventana(30, 900)
_mensajes_ip = Ventana(20, 3600)


def _acceso(db: Session, request: Request, token: str | None, bloquear: bool = False) -> m.CnAcceso:
    ip = ip_cliente(request) or "?"
    if _fallos_ip.excedida(ip):
        raise HTTPException(429, "Demasiados intentos. Espere unos minutos.")
    a = None
    if token and 20 <= len(token) <= 100:
        q = select(m.CnAcceso).where(m.CnAcceso.token_hash == sol.huella(token))
        a = db.scalar(q.with_for_update() if bloquear else q)
    if a is None:
        _fallos_ip.registrar(ip)
        raise HTTPException(404, "El enlace no es válido. Pida uno nuevo a su despacho.")
    if portal.estado(a) != "activo":
        raise HTTPException(410, "Este enlace ya no está vigente. Pida uno nuevo a su despacho.")
    org = db.get(m.Organizacion, a.organizacion_id)
    c = db.get(m.CrCliente, a.cliente_id)
    if not org or org.estado != "activa" or not c or c.organizacion_id != a.organizacion_id or "connect" not in modulos.activos(db, a.organizacion_id):
        raise HTTPException(410, "Este enlace ya no está disponible.")
    return a


def _verificado(a: m.CnAcceso, sesion: str | None) -> bool:
    return not a.requiere_codigo or portal.sesion_valida(sesion, a)


def _exigir(a: m.CnAcceso, sesion: str | None) -> None:
    if not _verificado(a, sesion):
        raise HTTPException(401, "Su verificación venció. Pida un código nuevo.")


def _seguimientos(db: Session, a: m.CnAcceso) -> list[tuple[m.CnSeguimiento, m.AgAsunto]]:
    """Solo asuntos DE ESTE cliente, de ESTE despacho, con seguimiento publicado."""
    q = (select(m.CnSeguimiento, m.AgAsunto).join(m.AgAsunto, m.AgAsunto.id == m.CnSeguimiento.asunto_id)
         .where(m.AgAsunto.cr_cliente_id == a.cliente_id, m.AgAsunto.organizacion_id == a.organizacion_id,
                m.CnSeguimiento.organizacion_id == a.organizacion_id, m.CnSeguimiento.visible_cliente.is_(True))
         .order_by(m.CnSeguimiento.estado, m.AgAsunto.titulo))
    return [(s, x) for s, x in db.execute(q).all()]


@router.post("/estado")
def estado(request: Request, x_enlace: str | None = Header(None), x_sesion: str | None = Header(None), db: Session = Depends(get_db)):
    a = _acceso(db, request, x_enlace)
    c = db.get(m.CrCliente, a.cliente_id)
    org = db.get(m.Organizacion, a.organizacion_id)
    base = {"despacho": org.nombre, "logo": bool(org.logo_actualizado), "nombre": c.nombre.split()[0] if c.tipo == "fisica" else c.nombre,
            "requiere_codigo": a.requiere_codigo, "email": sol.enmascarar(c.email) if c.email else None}
    if not _verificado(a, x_sesion):
        return {**base, "verificado": False}
    if not a.ultimo_uso_en or m.ahora() - sol._aware(a.ultimo_uso_en) > timedelta(minutes=30):
        a.visitas += 1
        auditar(db, None, "cn_portal_abierto", "cr_cliente", c.id, {}, request, organizacion_id=a.organizacion_id)
    a.ultimo_uso_en = m.ahora()
    segs = _seguimientos(db, a)
    asuntos = [cb.publico(db, s, x) for s, x in segs]
    pagos = None
    if any(s.mostrar_pagos for s, _ in segs):
        cargos = db.scalars(select(m.CrCargo).where(m.CrCargo.cliente_id == c.id, m.CrCargo.organizacion_id == a.organizacion_id)).all()
        pagosr = db.scalars(select(m.CrPago).where(m.CrPago.cliente_id == c.id, m.CrPago.organizacion_id == a.organizacion_id)).all()
        cta = cl.cuenta(list(cargos), list(pagosr), hoy())
        pagos = {"saldo": str(max(cta.saldo, 0)), "vencido": str(cta.vencido),
                 "pendientes": [{"concepto": x["concepto"], "pendiente": x["pendiente"], "vence": x["vence"], "estado": x["estado"]}
                                for x in cta.cargos if x["estado"] in ("pendiente", "parcial", "vencido")]}
    msgs = db.scalars(select(m.CnMensaje).where(m.CnMensaje.cliente_id == c.id, m.CnMensaje.organizacion_id == a.organizacion_id)
                      .order_by(m.CnMensaje.creado_en, m.CnMensaje.id)).all()
    nombres = {x.id: x.nombre for x in db.scalars(select(m.Usuario).where(m.Usuario.organizacion_id == a.organizacion_id))}
    titulos = {x.id: x.titulo for _, x in segs}
    no_leidos = 0
    for x in msgs:
        if x.autor == "despacho" and not x.leido_en:
            no_leidos += 1
    db.commit()
    return {**base, "verificado": True, "asuntos": asuntos, "pagos": pagos,
            "mensajes": [{"autor": x.autor, "texto": x.texto, "fecha": x.creado_en.isoformat(), "motivo": MOTIVOS.get(x.motivo or ""),
                          "atendido": x.estado == "atendido", "por": (nombres.get(x.usuario_id) or org.nombre) if x.autor == "despacho" else None,
                          "asunto": titulos.get(x.asunto_id)} for x in msgs[-100:]],
            "mensajes_nuevos": no_leidos, "motivos": MOTIVOS}


@router.post("/leido")
def leido(request: Request, x_enlace: str | None = Header(None), x_sesion: str | None = Header(None), db: Session = Depends(get_db)):
    a = _acceso(db, request, x_enlace)
    _exigir(a, x_sesion)
    for x in db.scalars(select(m.CnMensaje).where(m.CnMensaje.cliente_id == a.cliente_id, m.CnMensaje.autor == "despacho",
                                                  m.CnMensaje.leido_en.is_(None))):
        x.leido_en = m.ahora()
    db.commit()
    return {"ok": True}


@router.get("/logo")
def logo(request: Request, x_enlace: str | None = Header(None), db: Session = Depends(get_db)):
    a = _acceso(db, request, x_enlace)
    org = db.get(m.Organizacion, a.organizacion_id)
    if not org.logo:
        raise HTTPException(404, "Sin logotipo.")
    return Response(org.logo, media_type="image/png", headers={"Cache-Control": "private, max-age=600"})


@router.post("/codigo")
def codigo(request: Request, x_enlace: str | None = Header(None), db: Session = Depends(get_db)):
    a = _acceso(db, request, x_enlace, bloquear=True)
    c = db.get(m.CrCliente, a.cliente_id)
    if not a.requiere_codigo or not c.email:
        raise HTTPException(409, "Este enlace no necesita código.")
    if a.codigo_enviado_en and m.ahora() - sol._aware(a.codigo_enviado_en) < timedelta(seconds=sol.CODIGO_ESPERA_SEGUNDOS):
        raise HTTPException(429, "Ya le enviamos un código. Espere un minuto antes de pedir otro.")
    if a.codigos_enviados >= sol.CODIGOS_MAXIMOS:
        raise HTTPException(429, "Se pidieron demasiados códigos. Pida un enlace nuevo a su despacho.")
    cod = sol.nuevo_codigo()
    a.codigo_hash, a.codigo_expira_en = sol.huella_codigo(portal.DESFASE_CODIGO + a.id, cod), m.ahora() + timedelta(minutes=sol.CODIGO_MINUTOS)
    a.codigo_intentos, a.codigo_enviado_en, a.codigos_enviados = 0, m.ahora(), a.codigos_enviados + 1
    db.commit()
    org = db.get(m.Organizacion, a.organizacion_id)
    asunto, html, texto = plantillas_correo.codigo_verificacion(org.nombre, cod, sol.CODIGO_MINUTOS, portal=True)
    r = envios.registrar_y_enviar(db, "cn_codigo", [c.email], asunto, html, texto, organizacion_id=a.organizacion_id)
    if r.estado != "enviado":
        raise HTTPException(503, "No pudimos enviar el código en este momento. Intente más tarde o pida ayuda a su despacho.")
    return {"enviado": True, "email": sol.enmascarar(c.email), "minutos": sol.CODIGO_MINUTOS}


class Codigo(BaseModel):
    codigo: str = Field(min_length=4, max_length=12)


@router.post("/verificar")
def verificar(d: Codigo, request: Request, x_enlace: str | None = Header(None), db: Session = Depends(get_db)):
    a = _acceso(db, request, x_enlace, bloquear=True)
    if not a.requiere_codigo:
        return {"sesion": portal.crear_sesion(a)}
    if not a.codigo_hash:
        raise HTTPException(409, "Primero pida su código.")
    if a.codigo_intentos >= sol.CODIGO_INTENTOS:
        raise HTTPException(429, "Demasiados intentos. Pida un código nuevo.")
    ok = a.codigo_expira_en and sol._aware(a.codigo_expira_en) > m.ahora() and \
        hmac.compare_digest(a.codigo_hash, sol.huella_codigo(portal.DESFASE_CODIGO + a.id, d.codigo.strip()))
    if not ok:
        a.codigo_intentos += 1
        if a.codigo_intentos >= sol.CODIGO_INTENTOS:
            a.codigo_hash = None
        db.commit()
        _fallos_ip.registrar(ip_cliente(request) or "?")
        raise HTTPException(422, "El código no es correcto o ya venció.")
    a.codigo_hash = None
    auditar(db, None, "cn_portal_verificado", "cr_cliente", a.cliente_id, {}, request, organizacion_id=a.organizacion_id)
    db.commit()
    return {"sesion": portal.crear_sesion(a)}


class Mensaje(BaseModel):
    texto: str = Field(min_length=2, max_length=2000)
    motivo: str = "seguimiento"
    asunto_id: int | None = None  # id del SEGUIMIENTO que ve el cliente


@router.post("/mensajes", status_code=201)
def escribir(d: Mensaje, request: Request, x_enlace: str | None = Header(None), x_sesion: str | None = Header(None), db: Session = Depends(get_db)):
    a = _acceso(db, request, x_enlace, bloquear=True)
    _exigir(a, x_sesion)
    if d.motivo not in MOTIVOS:
        raise HTTPException(422, "Elija un motivo.")
    ip = ip_cliente(request) or "?"
    if _mensajes_ip.excedida(f"{ip}:{a.id}"):
        raise HTTPException(429, "Envió muchos mensajes seguidos. Espere un momento; su despacho ya los recibió.")
    abiertos = db.scalar(select(func.count(m.CnMensaje.id)).where(m.CnMensaje.cliente_id == a.cliente_id, m.CnMensaje.autor == "cliente",
                                                                  m.CnMensaje.estado == "nuevo")) or 0
    if abiertos >= 20:
        raise HTTPException(429, "Tiene muchos mensajes sin responder. Su despacho le contestará pronto.")
    asunto_id = None
    if d.asunto_id:
        segs = {s.id: x for s, x in _seguimientos(db, a)}
        if d.asunto_id not in segs:
            raise HTTPException(404, "No encontrado.")
        asunto_id = segs[d.asunto_id].id
    _mensajes_ip.registrar(f"{ip}:{a.id}")
    x = m.CnMensaje(organizacion_id=a.organizacion_id, cliente_id=a.cliente_id, asunto_id=asunto_id, autor="cliente", motivo=d.motivo,
                    texto=d.texto.strip(), estado="nuevo")
    db.add(x)
    db.flush()
    auditar(db, None, "cn_mensaje_cliente", "cr_cliente", a.cliente_id, {"mensaje_id": x.id, "motivo": d.motivo}, request,
            organizacion_id=a.organizacion_id)
    db.commit()
    _avisar_despacho(db, a, MOTIVOS[d.motivo], x.id)
    return {"ok": True, "mensaje": "Su mensaje llegó al despacho. Le responderán por aquí."}


def _avisar_despacho(db: Session, a: m.CnAcceso, motivo: str, mid: int) -> None:
    """Correo al responsable del cliente (o a los administradores). Sin el texto del mensaje. Si el correo no está
    configurado, el mensaje queda igual en la bandeja de Nomira."""
    c = db.get(m.CrCliente, a.cliente_id)
    dest = []
    if c.responsable_id:
        r = db.get(m.Usuario, c.responsable_id)
        if r and r.activo:
            dest = [r]
    if not dest:
        dest = list(db.scalars(select(m.Usuario).where(m.Usuario.organizacion_id == a.organizacion_id, m.Usuario.rol == "administrador",
                                                       m.Usuario.activo.is_(True)).limit(3)))
    url = ajustes().url_publica.rstrip("/") + f"/connect?cliente={c.id}"
    for u in dest:
        try:
            asunto, html, texto = plantillas_correo.mensaje_de_cliente(u.nombre, c.nombre, motivo, url)
            envios.registrar_y_enviar(db, "cn_mensaje_cliente", [u.email], asunto, html, texto, organizacion_id=a.organizacion_id,
                                      llave=f"cn_msg:{mid}:{u.id}")
        except Exception:  # el aviso por correo nunca impide que el mensaje quede guardado
            pass
