"""Propuesta comercial para el prospecto (enlace seguro) y webhook de Stripe.

El enlace es /propuesta#<token>: el token viaja en el fragmento (no llega a los registros del
servidor web ni a sitios de terceros) y la página lo manda en el encabezado X-Enlace.
Solo se muestra la última versión ENVIADA de esa cotización y nada interno.
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import ip_cliente
from ..freno import Ventana
from ..services import suscripciones as sus
from ..services.comercial import base as cm
from ..services.comercial import cupones
from ..services.comercial import pdf as cm_pdf
from ..services.comercial import stripe as st
from .comercial import _aplicar_pagos

router = APIRouter(tags=["Propuesta comercial (pública)"])
log = logging.getLogger("nomira.comercial")
_ver_ip = Ventana(60, 600)
_accion_ip = Ventana(10, 3600)
VISTA_CADA = timedelta(minutes=30)


def _freno(v: Ventana, request: Request) -> None:
    ip = ip_cliente(request) or "?"
    if v.excedida(ip):
        raise HTTPException(429, "Demasiadas solicitudes. Intente más tarde.")
    v.registrar(ip)


def _contacto(v: m.CmVersion | None, db: Session) -> dict:
    n = (v.nomira if v and v.nomira else None) or cm.datos_nomira(cm.config(db))
    return {"nombre": n.get("nombre_comercial") or "Nomira", "correo": n.get("correo_ventas"), "telefono": n.get("telefono"),
            "sitio_web": n.get("sitio_web")}


def _abrir(db: Session, token: str | None) -> tuple[m.CmCotizacion, m.CmVersion, dict | None]:
    """Devuelve la cotización, su versión enviada y, si no está disponible, el motivo."""
    c = cm.por_token(db, token)
    v = cm.version_enviada(db, c)
    if not v:
        raise HTTPException(404, "Este enlace no existe.")
    cm.actualizar_vencidas(db)
    if c.enlace_revocado_en:
        return c, v, {"motivo": "revocado", "mensaje": "Este enlace ya no está disponible."}
    if c.enlace_vence_en and c.enlace_vence_en < cm.ahora():
        return c, v, {"motivo": "enlace_vencido", "mensaje": "Este enlace ya venció."}
    if c.estado == "cancelada":
        return c, v, {"motivo": "cancelada", "mensaje": "Esta propuesta fue cancelada."}
    if c.estado == "vencida" or (c.estado in cm.ABIERTAS_CLIENTE and c.vence_en < cm.ahora()):
        return c, v, {"motivo": "vencida", "mensaje": "La vigencia de esta propuesta terminó."}
    return c, v, None


def _publica(c: m.CmCotizacion, v: m.CmVersion, db: Session) -> dict:
    nomira = v.nomira or {}
    formas = nomira.get("formas_pago") or []
    stripe_ok = cm.stripe_estado()["conectado"]
    e = v.entrada or {}
    calc = {**v.calculo}
    if calc.get("descuento"):  # el motivo del descuento es interno
        calc["descuento"] = {"importe": calc["descuento"]["importe"]}
    return {
        "folio": c.folio, "version": v.numero, "estado": c.estado, "estado_texto": cm.ESTADOS[c.estado], "huella": v.huella,
        "cliente": {"contacto": c.contacto, "despacho": c.despacho}, "necesidad": c.necesidad,
        "emision": e.get("emision"), "vence_en": c.vence_en.isoformat(), "calculo": calc,
        "condiciones": {"condiciones_pago": e.get("condiciones_pago"), "fecha_limite_pago": e.get("fecha_limite_pago"),
                        "terminos": e.get("terminos"), "observaciones": e.get("observaciones"), "generales": nomira.get("condiciones")},
        "nomira": {k: nomira.get(k) for k in ("nombre_comercial", "razon_social", "rfc", "domicilio", "correo_ventas", "telefono", "sitio_web",
                                              "instrucciones_contratar", "notas_pie")},
        "formas_pago": [{**f, "disponible": f["clave"] != "tarjeta" or stripe_ok,
                         **({"instrucciones": "Pago en línea pendiente de configuración."} if f["clave"] == "tarjeta" and not stripe_ok else {})}
                        for f in formas],
        "puede_aceptar": bool(nomira.get("aceptacion_en_linea")) and c.estado in cm.ABIERTAS_CLIENTE and c.vence_en > cm.ahora(),
        "puede_pedir_ajustes": c.estado in cm.ABIERTAS_CLIENTE and c.vence_en > cm.ahora(),
        "puede_pagar": c.estado in ("aceptada", "pendiente_pago"),
        "aceptada_en": c.aceptada_en.isoformat() if c.aceptada_en else None,
        "pagada": c.estado == "pagada",
    }


@router.post("/api/propuesta")
def ver(request: Request, x_enlace: str | None = Header(None), db: Session = Depends(get_db)):
    _freno(_ver_ip, request)
    c, v, no = _abrir(db, x_enlace)
    if no:
        db.commit()
        return {"disponible": False, **no, "folio": c.folio, "contacto": _contacto(v, db)}
    ultima = db.scalar(select(m.CmEvento).where(m.CmEvento.cotizacion_id == c.id, m.CmEvento.tipo == "vista", m.CmEvento.version == v.numero)
                       .order_by(m.CmEvento.creado_en.desc()))
    if not ultima or ultima.creado_en < cm.ahora() - VISTA_CADA:
        cm.evento(db, c, "vista", actor="cliente", version_num=v.numero)  # fecha, hora y versión; sin IP ni navegador
    if c.estado == "enviada":
        c.estado = "vista"
    c.vista_en = c.vista_en or cm.ahora()
    db.commit()
    return {"disponible": True, **_publica(c, v, db), "contacto": _contacto(v, db)}


@router.post("/api/propuesta/pdf")
def pdf(request: Request, x_enlace: str | None = Header(None), db: Session = Depends(get_db)):
    _freno(_ver_ip, request)
    c, v, no = _abrir(db, x_enlace)
    if no and no["motivo"] in ("revocado", "enlace_vencido", "cancelada"):
        raise HTTPException(410, no["mensaje"])
    contenido = cm_pdf.generar(folio=c.folio, version=v.numero, emision=v.entrada.get("emision"), vence_en=c.vence_en,
                               cliente={"contacto": c.contacto, "despacho": c.despacho, "email": c.email, "telefono": c.telefono},
                               necesidad=c.necesidad, calculo=v.calculo, entrada=v.entrada, nomira=v.nomira or {}, preparada_por=v.preparada_por)
    return Response(contenido, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{c.folio}-v{v.numero}.pdf"', "Cache-Control": "no-store"})


class AjusteIn(BaseModel):
    mensaje: str = Field(min_length=5, max_length=2000)


@router.post("/api/propuesta/ajustes")
def ajustes_(d: AjusteIn, request: Request, x_enlace: str | None = Header(None), db: Session = Depends(get_db)):
    _freno(_accion_ip, request)
    c, v, no = _abrir(db, x_enlace)
    if no or c.estado not in cm.ABIERTAS_CLIENTE:
        raise HTTPException(409, (no or {}).get("mensaje") or "Esta propuesta ya no admite solicitudes de ajuste.")
    cm.evento(db, c, "ajuste_solicitado", actor="cliente", version_num=v.numero, detalle={"mensaje": d.mensaje.strip()})
    c.actualizado_en = cm.ahora()
    db.commit()
    return {"ok": True, "mensaje": "Recibimos su solicitud. El equipo comercial le responderá; la propuesta no cambia hasta que le enviemos una nueva versión."}


class CuponIn(BaseModel):
    codigo: str = Field(min_length=3, max_length=40)


_cupon_ip = Ventana(15, 3600)


@router.post("/api/propuesta/cupon")
def aplicar_cupon(d: CuponIn, request: Request, x_enlace: str | None = Header(None), db: Session = Depends(get_db)):
    """El cliente aplica un código de descuento antes de aceptar. Se crea una versión nueva (mismos precios congelados
    con el cupón) que pasa a ser la que ve y acepta; la anterior queda en el historial."""
    _freno(_cupon_ip, request)
    c, v, no = _abrir(db, x_enlace)
    if no or c.estado not in cm.ABIERTAS_CLIENTE:
        raise HTTPException(409, (no or {}).get("mensaje") or "Los cupones se aplican antes de aceptar la propuesta.")
    if v.calculo.get("cupon"):
        raise HTTPException(409, f"Esta propuesta ya tiene el cupón {v.calculo['cupon']['codigo']}.")
    cupon = cupones.buscar(db, d.codigo, sus.hoy())
    calc = cupones.aplicar(v.calculo, cupon)
    numero = (db.scalar(select(func.max(m.CmVersion.numero)).where(m.CmVersion.cotizacion_id == c.id)) or 0) + 1
    nv = m.CmVersion(cotizacion_id=c.id, numero=numero, entrada={**v.entrada, "cupon": cupon.codigo}, nomira=v.nomira,
                     preparada_por=v.preparada_por, creado_por_id=None)
    cm.aplicar_calculo(nv, calc)
    db.add(nv)
    db.flush()
    nv.cambios = cm.cambios_entre(v, nv, None, c.vence_en)
    nv.huella = cm.huella_version(c, nv)
    nv.enviada_en = cm.ahora()
    c.version_actual, c.actualizado_en = numero, cm.ahora()
    cm.evento(db, c, "cupon_aplicado", actor="cliente", version_num=numero,
              detalle={"codigo": cupon.codigo, "importe": calc["cupon"]["importe"], "version_anterior": v.numero})
    db.commit()
    return {"ok": True, **_publica(c, nv, db)}


class AceptarIn(BaseModel):
    nombre: str = Field(min_length=3, max_length=200)
    cargo: str | None = Field(None, max_length=120)
    version: int
    acepto: bool


@router.post("/api/propuesta/aceptar")
def aceptar(d: AceptarIn, request: Request, x_enlace: str | None = Header(None), db: Session = Depends(get_db)):
    _freno(_accion_ip, request)
    c, v, no = _abrir(db, x_enlace)
    if no:
        raise HTTPException(409, no["mensaje"])
    if not (v.nomira or {}).get("aceptacion_en_linea"):
        raise HTTPException(409, "Esta propuesta no admite aceptación en línea. Comuníquese con el equipo comercial.")
    if c.estado not in cm.ABIERTAS_CLIENTE:
        raise HTTPException(409, "Esta propuesta ya no se puede aceptar.")
    if d.version != v.numero:
        raise HTTPException(409, "Hay una versión más reciente de la propuesta. Recargue la página para revisarla.")
    if not d.acepto:
        raise HTTPException(422, "Marque la casilla para registrar su aceptación.")
    c.estado, c.aceptada_en, c.actualizado_en = "aceptada", cm.ahora(), cm.ahora()
    cm.evento(db, c, "aceptada", actor="cliente", version_num=v.numero,
              detalle={"nombre": d.nombre.strip(), "cargo": (d.cargo or "").strip() or None, "version": v.numero, "huella": v.huella})
    db.commit()
    return {"ok": True, **_publica(c, v, db)}


class PagarIn(BaseModel):
    metodo: str
    referencia: str | None = Field(None, max_length=120)


@router.post("/api/propuesta/pagar")
def pagar(d: PagarIn, request: Request, x_enlace: str | None = Header(None), db: Session = Depends(get_db)):
    _freno(_accion_ip, request)
    c, v, no = _abrir(db, x_enlace)
    if no and no["motivo"] != "vencida":
        raise HTTPException(409, no["mensaje"])
    if c.estado not in ("aceptada", "pendiente_pago"):
        raise HTTPException(409, "Primero registre la aceptación de la propuesta.")
    formas = {f["clave"]: f for f in (v.nomira or {}).get("formas_pago") or []}
    if d.metodo not in formas:
        raise HTTPException(422, "Esa forma de pago no está disponible para esta propuesta.")
    if d.metodo == "tarjeta":
        if not cm.stripe_estado()["conectado"]:
            raise HTTPException(409, "Pago en línea pendiente de configuración.")
        intentos = db.query(m.CmPago).filter_by(cotizacion_id=c.id, metodo="tarjeta").count()
        p = m.CmPago(cotizacion_id=c.id, version=v.numero, metodo="tarjeta", estado="iniciado", monto=v.total)
        db.add(p)
        db.flush()
        base_url = ajustes().url_publica.rstrip("/")
        token = x_enlace
        try:
            s = st.crear_sesion(folio=c.folio, version=v.numero, cotizacion_id=c.id, pago_id=p.id, total=v.total, email=c.email,
                                url_exito=f"{base_url}/propuesta?pago=procesando#{token}", url_cancelar=f"{base_url}/propuesta?pago=cancelado#{token}",
                                idempotencia=f"nomira-cot-{c.id}-v{v.numero}-{intentos + 1}")
        except st.StripeError as e:
            db.rollback()
            raise HTTPException(502, str(e))
        p.stripe_sesion = s["id"]
        c.estado = "pendiente_pago"
        cm.evento(db, c, "pago_iniciado", actor="cliente", version_num=v.numero)
        db.commit()
        return {"url": s["url"]}
    # transferencia u otra forma: se registra la intención; NUNCA se marca pagada sin confirmación de Nomira
    c.estado, c.actualizado_en = "pendiente_pago", cm.ahora()
    cm.evento(db, c, "transferencia_reportada", actor="cliente", version_num=v.numero,
              detalle={"metodo": d.metodo, "referencia": (d.referencia or "").strip() or None})
    db.commit()
    return {"ok": True, "mensaje": "Gracias. Su pago se confirmará cuando el equipo de Nomira verifique la recepción."}


@router.post("/api/comercial/stripe/webhook")
async def stripe_webhook(request: Request, stripe_signature: str | None = Header(None), db: Session = Depends(get_db)):
    cuerpo = await request.body()
    if not st.firma_valida(cuerpo, stripe_signature):
        raise HTTPException(400, "Firma inválida.")
    try:
        ev = json.loads(cuerpo)
    except ValueError:
        raise HTTPException(400, "Cuerpo inválido.")
    real = cm.stripe_modo() == "real"
    if bool(ev.get("livemode")) != real:  # un evento de prueba nunca marca pagos reales, ni al revés
        log.warning("Se ignoró un evento de Stripe de otro modo (livemode=%s, STRIPE_MODO=%s).", bool(ev.get("livemode")), cm.stripe_modo())
        return {"ok": True, "ignorado": "modo_distinto"}
    try:
        with db.begin_nested():
            db.add(m.CmEventoStripe(evento_id=str(ev.get("id"))[:120], tipo=str(ev.get("type"))[:80]))
            db.flush()
    except IntegrityError:
        return {"ok": True, "duplicado": True}  # idempotencia: el mismo evento no se aplica dos veces
    if ev.get("type") in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        obj = (ev.get("data") or {}).get("object") or {}
        p = db.scalar(select(m.CmPago).where(m.CmPago.stripe_sesion == obj.get("id")))
        if p and obj.get("payment_status") == "paid" and p.estado != "confirmado":
            c = db.get(m.CmCotizacion, p.cotizacion_id)
            esperado = st.centavos(p.monto)
            if obj.get("amount_total") != esperado or (obj.get("currency") or "").lower() != "mxn":
                log.warning("Pago de Stripe con importe o moneda distintos (pago %s): no se aplicó.", p.id)
            elif c and c.estado not in ("cancelada",):
                p.estado, p.confirmado_en = "confirmado", cm.ahora()
                p.referencia = str(obj.get("payment_intent") or obj.get("id"))[:120]
                p.fecha_pago = cm.ahora().date()
                v = cm.version(db, c, p.version)
                cm.evento(db, c, "pago_registrado", actor="stripe", version_num=p.version,
                          detalle={"metodo": "tarjeta", "monto": cm.txt(p.monto), "modo": "real" if real else "prueba"})
                _aplicar_pagos(db, c, v, actor="stripe")
        if p is None and obj.get("payment_status") == "paid":
            if (obj.get("metadata") or {}).get("tipo") == "ia_paquete":
                _confirmar_paquete_ia(db, obj, real)
            else:
                _confirmar_compra_curso(db, obj, real)
    db.commit()
    return {"ok": True}


def _confirmar_paquete_ia(db: Session, obj: dict, real: bool) -> None:
    """Paquete extra de usos del Asistente IA: se suman solo con pago confirmado por el importe exacto."""
    paq = db.scalar(select(m.AsPaquete).where(m.AsPaquete.stripe_sesion == obj.get("id")))
    if not paq or paq.estado != "iniciada":
        return
    if obj.get("amount_total") != st.centavos(paq.total) or (obj.get("currency") or "").lower() != "mxn":
        log.warning("Paquete de IA con importe o moneda distintos (paquete %s): no se aplicó.", paq.id)
        return
    paq.estado, paq.pagada_en = "pagada", cm.ahora()
    paq.referencia = str(obj.get("payment_intent") or obj.get("id"))[:120]
    db.add(m.Auditoria(organizacion_id=paq.organizacion_id, usuario_id=paq.usuario_id, accion="ia_paquete_pagado", entidad="as_paquete",
                       entidad_id=paq.id, detalle={"usos": paq.usos, "total": cm.txt(paq.total), "modo": "real" if real else "prueba"}))


def _confirmar_compra_curso(db: Session, obj: dict, real: bool) -> None:
    """Compra en línea de un curso de Nomira (Academia): da acceso al despacho solo con pago confirmado."""
    from ..services.academia import lms

    compra = db.scalar(select(m.AcCompra).where(m.AcCompra.stripe_sesion == obj.get("id")))
    if not compra or compra.estado == "pagada":
        return
    if obj.get("amount_total") != st.centavos(compra.total) or (obj.get("currency") or "").lower() != "mxn":
        log.warning("Compra de curso con importe o moneda distintos (compra %s): no se aplicó.", compra.id)
        return
    curso = db.get(m.AcCurso, compra.curso_id)
    compra.estado, compra.pagada_en = "pagada", cm.ahora()
    compra.referencia = str(obj.get("payment_intent") or obj.get("id"))[:120]
    if curso:
        lms.otorgar(db, compra.organizacion_id, curso, "compra", compra_id=compra.id)
    db.add(m.Auditoria(organizacion_id=compra.organizacion_id, usuario_id=compra.usuario_id, accion="ac_curso_comprado", entidad="ac_curso",
                       entidad_id=compra.curso_id, detalle={"compra_id": compra.id, "total": cm.txt(compra.total), "modo": "real" if real else "prueba"}))
