"""Rutas públicas de Nomira AFORE:

1. Portal del cliente (/api/portal-afore/*): el cliente ve SOLO lo que el despacho decidió compartir de
   sus casos, los documentos que le faltan, sube documentos y cambia su preferencia de comunicación.
   Sin notas internas, análisis, otros clientes ni documentos no compartidos. El token va en X-Enlace.
2. Webhook de WhatsApp Business Platform (/api/whatsapp/webhook): valida la firma de Meta, procesa
   cada evento una sola vez (idempotencia) y nunca cambia el estado jurídico de un caso.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import unicodedata
from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, ip_cliente
from ..freno import Ventana
from ..services import envios, modulos, plantillas_correo
from ..services.afore import catalogos as cat
from ..services.afore import portal, whatsapp
from ..services.evidencia import solicitudes as sol
from .afore import guardar_archivo, tipos

router = APIRouter(tags=["Nomira AFORE — público"])
log = logging.getLogger("nomira.afore")
_fallos_ip = Ventana(30, 900)


# ---------- portal del cliente ----------

def _acceso(db: Session, request: Request, token: str | None, bloquear: bool = False) -> m.AfAcceso:
    ip = ip_cliente(request) or "?"
    if _fallos_ip.excedida(ip):
        raise HTTPException(429, "Demasiados intentos. Espere unos minutos.")
    a = None
    if token and 20 <= len(token) <= 100:
        q = select(m.AfAcceso).where(m.AfAcceso.token_hash == sol.huella(token))
        a = db.scalar(q.with_for_update() if bloquear else q)
    if a is None:
        _fallos_ip.registrar(ip)
        raise HTTPException(404, "El enlace no es válido. Pida uno nuevo a su despacho.")
    e = portal.estado(a)
    if e != "activo":
        raise HTTPException(410, "Este enlace ya no está vigente. Pida uno nuevo a su despacho.")
    org = db.get(m.Organizacion, a.organizacion_id)
    if not org or org.estado != "activa" or "afore" not in modulos.activos(db, a.organizacion_id):
        raise HTTPException(410, "Este enlace ya no está disponible.")
    return a


def _verificado(a: m.AfAcceso, sesion: str | None) -> bool:
    return not a.requiere_codigo or portal.sesion_valida(sesion, a)


@router.post("/api/portal-afore/estado")
def portal_estado(request: Request, x_enlace: str | None = Header(None), x_sesion: str | None = Header(None), db: Session = Depends(get_db)):
    a = _acceso(db, request, x_enlace)
    c = db.get(m.AfCliente, a.cliente_id)
    org = db.get(m.Organizacion, a.organizacion_id)
    base = {"despacho": org.nombre, "nombre": c.nombre.split()[0], "requiere_codigo": a.requiere_codigo,
            "email": sol.enmascarar(c.email) if c.email else None, "expira_en": a.expira_en.isoformat()}
    if not _verificado(a, x_sesion):
        return {**base, "verificado": False}
    if not a.ultimo_uso_en or m.ahora() - sol._aware(a.ultimo_uso_en) > timedelta(minutes=30):
        auditar(db, None, "af_portal_abierto", "af_cliente", c.id, {}, request, organizacion_id=a.organizacion_id)
    a.ultimo_uso_en = m.ahora()
    t = tipos(db, a.organizacion_id)
    casos = []
    for x in db.scalars(select(m.AfCaso).where(m.AfCaso.cliente_id == c.id, m.AfCaso.portal_visible.is_(True), m.AfCaso.estado != "borrador")
                        .order_by(m.AfCaso.id)):
        reqs = db.scalars(select(m.AfRequisito).where(m.AfRequisito.caso_id == x.id, m.AfRequisito.visible_cliente.is_(True),
                                                      m.AfRequisito.estado.in_(tuple(cat.ESTADOS_REQUISITO_CLIENTE))).order_by(m.AfRequisito.orden)).all()
        docs = db.scalars(select(m.AfDocumento).where(m.AfDocumento.caso_id == x.id,
                                                      (m.AfDocumento.visible_cliente.is_(True)) | (m.AfDocumento.origen == "cliente"))
                          .order_by(m.AfDocumento.id.desc())).all()
        casos.append({"id": x.id, "tramite": (x.tipo_otro or t.get(x.tipo_problema)) if x.tipo_problema == "otro" else t.get(x.tipo_problema),
                      "estado": x.estado_publico, "siguiente_paso": x.siguiente_paso_publico,
                      "actualizado_en": x.publico_actualizado_en.isoformat() if x.publico_actualizado_en else None,
                      "documentos_pedidos": [{"id": r.id, "nombre": r.nombre, "estado": cat.ESTADOS_REQUISITO_CLIENTE[r.estado],
                                              "pendiente": r.estado in ("solicitado", "requiere_correccion"), "indicacion": r.nota_cliente} for r in reqs],
                      "documentos": [{"nombre": d.nombre_original, "fecha": d.creado_en.isoformat(), "enviado_por_usted": d.origen == "cliente",
                                      "recepcion_confirmada_en": d.recepcion_confirmada_en.isoformat() if d.recepcion_confirmada_en else None}
                                     for d in docs]})
    cons = {k: bool(db.scalar(select(m.AfConsentimiento.id).where(m.AfConsentimiento.cliente_id == c.id, m.AfConsentimiento.canal == k,
                                                                  m.AfConsentimiento.revocado_en.is_(None)))) for k in ("whatsapp", "correo")}
    db.commit()
    return {**base, "verificado": True, "casos": casos, "preferencias": {"consentimientos": cons, "preferencia": c.preferencia_contacto,
                                                                         "tiene_telefono": bool(c.telefono), "tiene_correo": bool(c.email)}}


@router.post("/api/portal-afore/codigo")
def portal_codigo(request: Request, x_enlace: str | None = Header(None), db: Session = Depends(get_db)):
    a = _acceso(db, request, x_enlace, bloquear=True)
    c = db.get(m.AfCliente, a.cliente_id)
    if not a.requiere_codigo or not c.email:
        raise HTTPException(409, "Este enlace no necesita código.")
    if a.codigo_enviado_en and m.ahora() - sol._aware(a.codigo_enviado_en) < timedelta(seconds=sol.CODIGO_ESPERA_SEGUNDOS):
        raise HTTPException(429, "Ya le enviamos un código. Espere un minuto antes de pedir otro.")
    if a.codigos_enviados >= sol.CODIGOS_MAXIMOS:
        raise HTTPException(429, "Se pidieron demasiados códigos. Pida un enlace nuevo a su despacho.")
    codigo = sol.nuevo_codigo()
    a.codigo_hash, a.codigo_expira_en = sol.huella_codigo(10_000_000 + a.id, codigo), m.ahora() + timedelta(minutes=sol.CODIGO_MINUTOS)
    a.codigo_intentos, a.codigo_enviado_en, a.codigos_enviados = 0, m.ahora(), a.codigos_enviados + 1
    db.commit()
    org = db.get(m.Organizacion, a.organizacion_id)
    asunto, html, texto = plantillas_correo.codigo_verificacion(org.nombre, codigo, sol.CODIGO_MINUTOS)
    r = envios.registrar_y_enviar(db, "af_codigo", [c.email], asunto, html, texto, organizacion_id=a.organizacion_id)
    if r.estado != "enviado":
        raise HTTPException(503, "No pudimos enviar el código en este momento. Intente más tarde.")
    return {"enviado": True, "email": sol.enmascarar(c.email), "minutos": sol.CODIGO_MINUTOS}


class Codigo(BaseModel):
    codigo: str = Field(min_length=4, max_length=12)


@router.post("/api/portal-afore/verificar")
def portal_verificar(d: Codigo, request: Request, x_enlace: str | None = Header(None), db: Session = Depends(get_db)):
    a = _acceso(db, request, x_enlace, bloquear=True)
    if not a.requiere_codigo:
        return {"sesion": portal.crear_sesion(a)}
    if not a.codigo_hash:
        raise HTTPException(409, "Primero pida su código.")
    if a.codigo_intentos >= sol.CODIGO_INTENTOS:
        raise HTTPException(429, "Demasiados intentos. Pida un código nuevo.")
    import hmac

    ok = a.codigo_expira_en and sol._aware(a.codigo_expira_en) > m.ahora() and \
        hmac.compare_digest(a.codigo_hash, sol.huella_codigo(10_000_000 + a.id, d.codigo.strip()))
    if not ok:
        a.codigo_intentos += 1
        if a.codigo_intentos >= sol.CODIGO_INTENTOS:
            a.codigo_hash = None
        db.commit()
        _fallos_ip.registrar(ip_cliente(request) or "?")
        raise HTTPException(422, "El código no es correcto o ya venció.")
    a.codigo_hash = None
    auditar(db, None, "af_portal_verificado", "af_cliente", a.cliente_id, {}, request, organizacion_id=a.organizacion_id)
    db.commit()
    return {"sesion": portal.crear_sesion(a)}


@router.post("/api/portal-afore/documentos", status_code=201)
def portal_subir(request: Request, archivo: UploadFile = File(...), requisito_id: int = Form(...), x_enlace: str | None = Header(None),
                 x_sesion: str | None = Header(None), db: Session = Depends(get_db)):
    """El cliente sube un documento EN RESPUESTA a algo que el despacho le pidió."""
    a = _acceso(db, request, x_enlace, bloquear=True)
    if not _verificado(a, x_sesion):
        raise HTTPException(401, "Su verificación venció. Pida un código nuevo.")
    r = db.get(m.AfRequisito, requisito_id)
    caso = db.get(m.AfCaso, r.caso_id) if r else None
    if (not r or not caso or caso.cliente_id != a.cliente_id or not caso.portal_visible or not r.visible_cliente
            or r.estado not in ("solicitado", "requiere_correccion", "recibido", "por_revisar")):
        raise HTTPException(404, "No encontrado.")
    nombre = os.path.basename((archivo.filename or "documento").replace("\\", "/"))[:300]
    if os.path.splitext(nombre.lower())[1] not in (".pdf", ".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(415, "Solo se aceptan archivos PDF, JPG, PNG o WebP.")
    n = db.scalar(select(m.AfDocumento.id).where(m.AfDocumento.caso_id == caso.id, m.AfDocumento.origen == "cliente").order_by(m.AfDocumento.id.desc()).offset(49))
    if n:
        raise HTTPException(409, "Se alcanzó el máximo de documentos para este trámite. Contacte a su despacho.")
    ruta, formato, datos, sha = guardar_archivo(db, caso, archivo)
    d = m.AfDocumento(organizacion_id=caso.organizacion_id, caso_id=caso.id, requisito_id=r.id, nombre_original=nombre, sha256=sha, ruta=ruta,
                      formato=formato, tamano_bytes=len(datos), origen="cliente", visible_cliente=False, estado="recibido")
    db.add(d)
    r.estado, r.actualizado_en = "recibido", m.ahora()
    db.flush()
    auditar(db, None, "af_documento_recibido_cliente", "af_documento", d.id, {"caso_id": caso.id, "sha256": sha}, request,
            organizacion_id=caso.organizacion_id)
    db.commit()
    return {"ok": True, "nombre": nombre, "mensaje": "Recibimos su documento. El despacho confirmará su recepción."}


class Preferencias(BaseModel):
    whatsapp: bool | None = None
    correo: bool | None = None
    preferencia: str | None = None


@router.post("/api/portal-afore/preferencias")
def portal_preferencias(d: Preferencias, request: Request, x_enlace: str | None = Header(None), x_sesion: str | None = Header(None),
                        db: Session = Depends(get_db)):
    """El cliente da o retira su consentimiento por canal; queda registrado con fecha y medio «portal»."""
    a = _acceso(db, request, x_enlace)
    if not _verificado(a, x_sesion):
        raise HTTPException(401, "Su verificación venció.")
    c = db.get(m.AfCliente, a.cliente_id)
    for canal in ("whatsapp", "correo"):
        quiere = getattr(d, canal)
        if quiere is None:
            continue
        vigente = db.scalar(select(m.AfConsentimiento).where(m.AfConsentimiento.cliente_id == c.id, m.AfConsentimiento.canal == canal,
                                                             m.AfConsentimiento.revocado_en.is_(None)))
        if quiere and not vigente:
            if canal == "whatsapp" and not c.telefono or canal == "correo" and not c.email:
                raise HTTPException(422, f"El despacho no tiene registrado su {'teléfono' if canal == 'whatsapp' else 'correo'}.")
            db.add(m.AfConsentimiento(organizacion_id=c.organizacion_id, cliente_id=c.id, canal=canal, medio="portal",
                                      alcance="Actualizaciones de su trámite (otorgado por el cliente en su portal)"))
        elif not quiere and vigente:
            vigente.revocado_en, vigente.revocado_medio = m.ahora(), "portal"
        auditar(db, None, "af_consentimiento_portal", "af_cliente", c.id, {"canal": canal, "otorga": quiere}, request,
                organizacion_id=c.organizacion_id)
    if d.preferencia:
        if d.preferencia not in cat.CONTACTO:
            raise HTTPException(422, "Preferencia inválida.")
        c.preferencia_contacto = d.preferencia
    db.commit()
    return {"ok": True}


# ---------- webhook de WhatsApp (Cloud API oficial) ----------

@router.get("/api/whatsapp/webhook")
def webhook_verificar(modo: str | None = Query(None, alias="hub.mode"), token: str | None = Query(None, alias="hub.verify_token"),
                      reto: str | None = Query(None, alias="hub.challenge")):
    esperado = ajustes().whatsapp_verify_token
    if modo == "subscribe" and esperado and token and __import__("hmac").compare_digest(token, esperado):
        return Response(reto or "", media_type="text/plain")
    raise HTTPException(403, "Verificación inválida.")


ESTADOS_WA = {"sent": "enviado", "delivered": "entregado", "read": "leido", "failed": "fallido"}
_ORDEN = ["enviado", "entregado", "leido"]


def _plano(t: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", t.lower().strip()) if unicodedata.category(ch) != "Mn")


def _primera_vez(db: Session, llave: str) -> bool:
    try:
        with db.begin_nested():
            db.add(m.AfEventoWebhook(llave=llave[:200]))
            db.flush()
        return True
    except IntegrityError:
        return False


@router.post("/api/whatsapp/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    cuerpo = await request.body()
    if not whatsapp.firma_valida(cuerpo, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(401, "Firma inválida.")
    try:
        datos = json.loads(cuerpo)
    except ValueError:
        raise HTTPException(400, "JSON inválido.")
    for entrada in datos.get("entry", []):
        for cambio in entrada.get("changes", []):
            v = cambio.get("value") or {}
            pid = (v.get("metadata") or {}).get("phone_number_id")
            cfg = db.scalar(select(m.AfConfig).where(m.AfConfig.wa_phone_number_id == pid)) if pid else None
            if cfg is None:
                continue  # número que no pertenece a ningún despacho
            for st in v.get("statuses", []):
                _estado_mensaje(db, cfg, st)
            for mensaje in v.get("messages", []):
                _mensaje_entrante(db, cfg, mensaje)
    db.commit()
    return {"ok": True}  # 200 rápido: Meta reintenta si no lo recibe


def _estado_mensaje(db: Session, cfg: m.AfConfig, st: dict):
    wamid, estado = st.get("id"), ESTADOS_WA.get(st.get("status") or "")
    if not wamid or not estado or not _primera_vez(db, f"st:{wamid}:{estado}"):
        return
    x = db.scalar(select(m.AfMensaje).where(m.AfMensaje.proveedor_id == wamid, m.AfMensaje.organizacion_id == cfg.organizacion_id))
    if not x:
        return
    ahora = m.ahora()
    if estado == "fallido":
        x.estado = "fallido"
        x.error = "; ".join((e.get("title") or e.get("message") or "") for e in st.get("errors", []))[:1000] or "WhatsApp informó una falla."
    elif x.estado not in _ORDEN or _ORDEN.index(estado) > _ORDEN.index(x.estado):
        x.estado = estado  # los avisos pueden llegar desordenados: nunca se retrocede
    if estado == "entregado":
        x.entregado_en = x.entregado_en or ahora
    if estado == "leido":
        x.leido_en = x.leido_en or ahora


def _mensaje_entrante(db: Session, cfg: m.AfConfig, mensaje: dict):
    wamid = mensaje.get("id")
    if not wamid or not _primera_vez(db, f"in:{wamid}"):
        return
    org = cfg.organizacion_id
    tel = "".join(ch for ch in (mensaje.get("from") or "") if ch.isdigit())
    texto = ((mensaje.get("text") or {}).get("body") or f"[{mensaje.get('type', 'mensaje')} sin texto]")[:4000]
    # Se asocia solo si hay certeza: un único cliente con ese teléfono y, para el caso, un único caso abierto
    clientes = [c for c in db.scalars(select(m.AfCliente).where(m.AfCliente.organizacion_id == org)) if c.telefono and c.telefono[-10:] == tel[-10:]]
    cliente = clientes[0] if len(clientes) == 1 else None
    caso = None
    if cliente:
        abiertos = db.scalars(select(m.AfCaso).where(m.AfCaso.cliente_id == cliente.id, m.AfCaso.estado.notin_(("cerrado", "borrador")))).all()
        caso = abiertos[0] if len(abiertos) == 1 else None
    x = m.AfMensaje(organizacion_id=org, cliente_id=cliente.id if cliente else None, caso_id=caso.id if caso else None, canal="whatsapp",
                    direccion="entrante", texto=texto, estado="recibido" if cliente and caso else "por_asignar", telefono=tel,
                    proveedor_id=wamid, origen="whatsapp")
    db.add(x)
    # «BAJA»: el cliente deja de recibir WhatsApp (preferencia de comunicación, no un cambio en su caso)
    if cliente and _plano(texto) in ("baja", "stop", "cancelar", "no mas mensajes"):
        for c in db.scalars(select(m.AfConsentimiento).where(m.AfConsentimiento.cliente_id == cliente.id, m.AfConsentimiento.canal == "whatsapp",
                                                             m.AfConsentimiento.revocado_en.is_(None))):
            c.revocado_en, c.revocado_medio = m.ahora(), "mensaje"
    db.flush()
