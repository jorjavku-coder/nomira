"""Compra directa de módulos desde «Datos y módulos».

- Durante la prueba gratuita, encender un módulo no cuesta: se prueba hasta que termine la prueba.
- Fuera de la prueba, el administrador contrata con tarjeta en Stripe (suscripción mensual con cargo automático).
  El módulo se enciende SOLO cuando Stripe confirma el pago por webhook, por el importe exacto.
- Si la suscripción se cancela (por el cliente o porque Stripe agotó los reintentos de cobro), el módulo se apaga.
  Los datos nunca se borran.
- Los módulos que Nomira contrata por convenio (panel) no pasan por aquí.
"""
from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from . import modulos
from .comercial import base as cm

log = logging.getLogger("nomira.modulos")
CENT = Decimal("0.01")


def precio(db: Session, clave: str) -> dict | None:
    if not db.scalar(select(m.CmPrecio.id).limit(1)):
        cm.asegurar_catalogo(db)  # base nueva: precios iniciales (nunca pisa los que Nomira ya editó)
    p = db.scalar(select(m.CmPrecio).where(m.CmPrecio.clave == f"modulo:{clave}", m.CmPrecio.activo.is_(True)))
    if not p:
        return None
    iva_pct = cm.config(db).iva_pct
    iva = (p.precio_mensual * iva_pct / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    return {"precio": p.precio_mensual, "iva": iva, "total": p.precio_mensual + iva, "iva_pct": iva_pct}


def en_prueba(db: Session, org: m.Organizacion) -> bool:
    from . import registro
    e = registro.estado_prueba(db, org)
    return bool(e and e["estado"] == "prueba")


def vigente(db: Session, oid: int, clave: str) -> m.MdSuscripcion | None:
    return db.scalar(select(m.MdSuscripcion).where(m.MdSuscripcion.organizacion_id == oid, m.MdSuscripcion.modulo == clave,
                                                   m.MdSuscripcion.estado.in_(("activa", "pago_fallido", "cancelando")))
                     .order_by(m.MdSuscripcion.id.desc()).limit(1))


def catalogo(db: Session, org: m.Organizacion) -> dict:
    est = modulos.estado(db, org.id)
    prueba = en_prueba(db, org)
    filas = []
    for clave, x in est.items():
        p = precio(db, clave)
        s = vigente(db, org.id, clave)
        filas.append({**x, "precio": cm.txt(p["precio"]) if p else None, "iva": cm.txt(p["iva"]) if p else None,
                      "total": cm.txt(p["total"]) if p else None,
                      "suscripcion": {"estado": s.estado, "desde": s.activada_en.isoformat() if s.activada_en else None} if s else None,
                      "de_prueba": prueba and clave in (org.modulos_prueba or [])})
    return {"modulos": filas, "en_prueba": prueba, "pago_en_linea": cm.stripe_estado()["conectado"]}


def activar_en_prueba(db: Session, org: m.Organizacion, clave: str) -> None:
    modulos.fijar(db, org.id, clave, contratado=True, activo=True)
    org.modulos_prueba = list(dict.fromkeys([*(org.modulos_prueba or []), clave]))


def confirmar_pago(db: Session, obj: dict, real: bool) -> None:
    """checkout.session.completed de una suscripción de módulo: enciende el módulo con el importe exacto."""
    s = db.scalar(select(m.MdSuscripcion).where(m.MdSuscripcion.stripe_sesion == obj.get("id")))
    if not s or s.estado != "iniciada":
        return
    if obj.get("amount_total") != int((s.total * 100).to_integral_value()) or (obj.get("currency") or "").lower() != "mxn":
        log.warning("Suscripción de módulo con importe o moneda distintos (suscripción %s): no se aplicó.", s.id)
        return
    s.estado, s.activada_en, s.modo = "activa", m.ahora(), "real" if real else "prueba"
    s.stripe_suscripcion = str(obj.get("subscription") or "")[:120] or None
    modulos.fijar(db, s.organizacion_id, s.modulo, contratado=True, activo=True)
    db.add(m.Auditoria(organizacion_id=s.organizacion_id, usuario_id=s.usuario_id, accion="modulo_contratado_en_linea", entidad="md_suscripcion",
                       entidad_id=s.id, detalle={"modulo": s.modulo, "modo": s.modo}))


def evento_suscripcion(db: Session, tipo: str, obj: dict) -> None:
    """Cambios que avisa Stripe después de contratar: cobro fallido, cobro hecho, cancelación definitiva."""
    sid = obj.get("subscription") if tipo.startswith("invoice.") else obj.get("id")
    if not sid:
        return
    s = db.scalar(select(m.MdSuscripcion).where(m.MdSuscripcion.stripe_suscripcion == str(sid)).order_by(m.MdSuscripcion.id.desc()).limit(1))
    if not s or s.estado == "cancelada":
        return
    if tipo == "invoice.payment_failed":
        s.estado = "pago_fallido"  # Stripe reintenta; si no logra cobrar, cancela y llega customer.subscription.deleted
    elif tipo == "invoice.paid" and s.estado == "pago_fallido":
        s.estado = "activa"
    elif tipo == "customer.subscription.deleted":
        s.estado, s.cancelada_en = "cancelada", m.ahora()
        try:
            modulos.fijar(db, s.organizacion_id, s.modulo, contratado=False, activo=False)
        except Exception:  # p. ej. era el único módulo activo: queda contratado pero se registra
            log.warning("No se pudo apagar el módulo %s de la organización %s al cancelarse.", s.modulo, s.organizacion_id)
        db.add(m.Auditoria(organizacion_id=s.organizacion_id, usuario_id=None, accion="modulo_suscripcion_cancelada", entidad="md_suscripcion",
                           entidad_id=s.id, detalle={"modulo": s.modulo}))
