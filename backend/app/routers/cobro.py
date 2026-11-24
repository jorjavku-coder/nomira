"""Cobro en línea (ligas de pago con el Stripe del despacho) y factura electrónica CFDI 4.0 (con el Facturapi del despacho).

Funciona solo cuando el despacho conecta sus propias cuentas. Las llaves se guardan cifradas y nunca se devuelven.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, condecimal
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import auditar, puede_editar, solo_admin, usuario_actual
from ..services.agenda.base import hoy
from ..services.clientes import base as cb, cobro as cob

router = APIRouter(prefix="/api/cobro", tags=["Cobro en línea y facturación"])


def _cfg_dict(c: m.CrConfigCobro) -> dict:
    return {"stripe": {"conectado": bool(c.stripe_llave_cifrada), "pista": c.stripe_pista, "prueba": cob.es_prueba(c.stripe_pista)},
            "facturapi": {"conectado": bool(c.facturapi_llave_cifrada), "pista": c.facturapi_pista, "prueba": cob.es_prueba(c.facturapi_pista)},
            "clave_producto": c.clave_producto, "clave_unidad": c.clave_unidad, "uso_cfdi": c.uso_cfdi, "retenciones": c.retenciones,
            "usos": cob.USOS, "opciones_retenciones": cob.RETENCIONES, "motivos_cancelacion": cob.MOTIVOS_CANCELACION}


def _cliente(db: Session, cid: int, u: m.Usuario) -> m.CrCliente:
    c = cb.de_org(db, cid, u.organizacion_id)
    if not c:
        raise HTTPException(404, "Cliente no encontrado.")
    return c


def _err(e: cob.ErrorCobro) -> HTTPException:
    return HTTPException(422, str(e))


@router.get("/config")
def ver_config(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = cob.config(db, u.organizacion_id)
    db.commit()
    return {**_cfg_dict(c), "es_admin": u.rol == "administrador"}


class ConfigIn(BaseModel):
    stripe_llave: str | None = Field(None, max_length=300)  # None: sin cambio; "": desconectar
    facturapi_llave: str | None = Field(None, max_length=300)
    clave_producto: str | None = Field(None, pattern=r"^\d{8}$")
    clave_unidad: str | None = Field(None, pattern=r"^[A-Z0-9]{2,3}$")
    uso_cfdi: str | None = None
    retenciones: str | None = None


@router.put("/config")
def guardar_config(d: ConfigIn, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    c = cob.config(db, u.organizacion_id)
    stripe = d.stripe_llave.strip() if d.stripe_llave is not None else None
    facturapi = d.facturapi_llave.strip() if d.facturapi_llave is not None else None
    try:
        if stripe:
            cob.stripe_validar(stripe)
        if facturapi:
            cob.facturapi_validar(facturapi)
    except cob.ErrorCobro as e:
        raise _err(e)
    if d.uso_cfdi is not None and d.uso_cfdi not in cob.USOS:
        raise HTTPException(422, "Uso de CFDI no válido.")
    if d.retenciones is not None and d.retenciones not in cob.RETENCIONES:
        raise HTTPException(422, "Opción de retenciones no válida.")
    cob.guardar_llaves(c, stripe, facturapi)
    for k in ("clave_producto", "clave_unidad", "uso_cfdi", "retenciones"):
        v = getattr(d, k)
        if v is not None:
            setattr(c, k, v)
    c.actualizado_en = datetime.now(timezone.utc)
    cambios = [k for k, v in (("stripe", stripe), ("facturapi", facturapi)) if v is not None]
    auditar(db, u, "cobro_configuracion", "cr_config_cobro", c.id, {"llaves": cambios}, request)  # nunca la llave
    db.commit()
    return {**_cfg_dict(c), "es_admin": True}


def _liga_dict(x: m.CrLigaPago) -> dict:
    return {"id": x.id, "concepto": x.concepto, "monto": str(x.monto), "url": x.url if x.estado == "pendiente" else None, "estado": x.estado,
            "cargo_id": x.cargo_id, "pago_id": x.pago_id, "creado_en": x.creado_en.isoformat(),
            "expira_en": x.expira_en.isoformat() if x.expira_en else None, "pagada_en": x.pagada_en.isoformat() if x.pagada_en else None}


def _factura_dict(f: m.CrFactura) -> dict:
    return {"id": f.id, "pago_id": f.pago_id, "uuid": f.uuid, "serie_folio": f.serie_folio, "subtotal": str(f.subtotal), "total": str(f.total),
            "uso": f.uso, "estado": f.estado, "prueba": f.prueba, "creado_en": f.creado_en.isoformat(),
            "cancelada_en": f.cancelada_en.isoformat() if f.cancelada_en else None}


@router.get("/clientes/{cid}")
def de_cliente(cid: int, sincronizar: bool = True, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = _cliente(db, cid, u)
    cfg = cob.config(db, u.organizacion_id)
    nuevos = cob.sincronizar_pendientes(db, u.organizacion_id, c.id) if sincronizar and cfg.stripe_llave_cifrada else 0
    ligas = db.scalars(select(m.CrLigaPago).where(m.CrLigaPago.cliente_id == c.id).order_by(m.CrLigaPago.id.desc()).limit(30)).all()
    facturas = db.scalars(select(m.CrFactura).where(m.CrFactura.cliente_id == c.id).order_by(m.CrFactura.id.desc())).all()
    db.commit()
    return {"stripe": bool(cfg.stripe_llave_cifrada), "stripe_prueba": cob.es_prueba(cfg.stripe_pista),
            "facturapi": bool(cfg.facturapi_llave_cifrada), "facturapi_prueba": cob.es_prueba(cfg.facturapi_pista),
            "faltantes_factura": cob.faltantes(c, cfg), "uso_cfdi": cfg.uso_cfdi, "usos": cob.USOS, "motivos_cancelacion": cob.MOTIVOS_CANCELACION,
            "ligas": [_liga_dict(x) for x in ligas], "facturas": [_factura_dict(f) for f in facturas], "pagos_nuevos": nuevos}


class LigaIn(BaseModel):
    cargo_id: int | None = None
    monto: condecimal(gt=0, max_digits=12, decimal_places=2) | None = None
    concepto: str | None = Field(None, max_length=250)


@router.post("/clientes/{cid}/ligas", status_code=201)
def crear_liga(cid: int, d: LigaIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _cliente(db, cid, u)
    cfg = cob.config(db, u.organizacion_id)
    cargos = list(db.scalars(select(m.CrCargo).where(m.CrCargo.cliente_id == c.id)))
    pagos = list(db.scalars(select(m.CrPago).where(m.CrPago.cliente_id == c.id)))
    cta = cb.cuenta(cargos, pagos, hoy())
    cargo = None
    if d.cargo_id:
        cargo = next((g for g in cargos if g.id == d.cargo_id and not g.cancelado_en), None)
        if not cargo:
            raise HTTPException(422, "Ese cargo no es de este cliente.")
        pendiente = Decimal(next(x["pendiente"] for x in cta.cargos if x["id"] == cargo.id))
        concepto = d.concepto or cargo.concepto
    else:
        pendiente = max(cta.saldo, Decimal("0"))
        concepto = d.concepto or "Honorarios"
    monto = d.monto or pendiente
    if monto > pendiente:
        raise HTTPException(422, f"El monto no puede ser mayor a lo pendiente (${pendiente:,.2f}).")
    despacho = db.get(m.Organizacion, u.organizacion_id).nombre
    try:
        liga = cob.crear_liga(db, cfg, c, cargo, concepto, monto, despacho, u.id)
    except cob.ErrorCobro as e:
        raise _err(e)
    auditar(db, u, "cobro_liga", "cr_cliente", c.id, {"liga": liga.id, "monto": str(monto)}, request)
    db.commit()
    return _liga_dict(liga)


@router.post("/ligas/{lid}/cancelar")
def cancelar_liga(lid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    x = db.get(m.CrLigaPago, lid)
    if not x or x.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "Liga no encontrada.")
    cob.sincronizar_liga(db, x)
    if x.estado != "pendiente":
        db.commit()
        raise HTTPException(409, "La liga ya no está pendiente" + (": el cliente ya pagó." if x.estado == "pagada" else "."))
    cfg = cob.config(db, u.organizacion_id)
    try:
        r = httpx.post(f"{cob.STRIPE}/checkout/sessions/{x.stripe_sesion}/expire", auth=(cob.stripe_llave(cfg), ""), timeout=15)
    except (httpx.HTTPError, cob.ErrorCobro):
        raise HTTPException(502, "No se pudo desactivar la liga en Stripe. Intente de nuevo.")
    if r.status_code >= 300:
        cob.sincronizar_liga(db, x)
        db.commit()
        if x.estado == "pagada":
            raise HTTPException(409, "El cliente ya pagó esta liga.")
        raise HTTPException(502, "Stripe no permitió desactivar la liga.")
    x.estado = "cancelada"
    auditar(db, u, "cobro_liga_cancelada", "cr_cliente", x.cliente_id, {"liga": x.id}, request)
    db.commit()
    return _liga_dict(x)


class FacturaIn(BaseModel):
    uso: str | None = None
    concepto: str | None = Field(None, max_length=1000)


@router.get("/pagos/{pid}/desglose")
def ver_desglose(pid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    p = db.get(m.CrPago, pid)
    if not p or p.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "Pago no encontrado.")
    c = db.get(m.CrCliente, p.cliente_id)
    cfg = cob.config(db, u.organizacion_id)
    d = cob.desglose(p.monto, cfg.retenciones, c.tipo == "moral")
    return {k: str(v) for k, v in d.items()}


@router.post("/pagos/{pid}/factura", status_code=201)
def facturar(pid: int, d: FacturaIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    p = db.get(m.CrPago, pid)
    if not p or p.organizacion_id != u.organizacion_id or p.cancelado_en:
        raise HTTPException(404, "Pago no encontrado o cancelado.")
    if db.scalar(select(m.CrFactura.id).where(m.CrFactura.pago_id == p.id, m.CrFactura.estado != "cancelada")):
        raise HTTPException(409, "Ese pago ya tiene una factura vigente.")
    c = db.get(m.CrCliente, p.cliente_id)
    cfg = cob.config(db, u.organizacion_id)
    uso = d.uso or cfg.uso_cfdi
    if uso not in cob.USOS:
        raise HTTPException(422, "Uso de CFDI no válido.")
    concepto = d.concepto
    if not concepto:
        g = db.get(m.CrCargo, p.cargo_id) if p.cargo_id else None
        concepto = f"Servicios profesionales jurídicos{': ' + g.concepto if g else ''}"
    try:
        f = cob.timbrar(db, cfg, c, p, concepto, uso, u.id)
    except cob.ErrorCobro as e:
        raise _err(e)
    auditar(db, u, "cobro_factura", "cr_cliente", c.id, {"factura": f.id, "pago_folio": p.folio}, request)
    db.commit()
    return _factura_dict(f)


def _factura(db: Session, fid: int, u: m.Usuario) -> tuple[m.CrFactura, m.CrConfigCobro]:
    f = db.get(m.CrFactura, fid)
    if not f or f.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "Factura no encontrada.")
    return f, cob.config(db, u.organizacion_id)


@router.get("/facturas/{fid}/{formato}")
def descargar(fid: int, formato: str, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    if formato not in ("pdf", "xml"):
        raise HTTPException(404, "Formato no disponible.")
    f, cfg = _factura(db, fid, u)
    try:
        datos = cob.archivo(cfg, f, formato)
    except cob.ErrorCobro as e:
        raise HTTPException(502, str(e))
    nombre = f"factura-{f.serie_folio or f.id}.{formato}"
    return Response(datos, media_type="application/pdf" if formato == "pdf" else "application/xml",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


class EnviarIn(BaseModel):
    email: str | None = Field(None, max_length=254)


@router.post("/facturas/{fid}/enviar")
def enviar(fid: int, d: EnviarIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    f, cfg = _factura(db, fid, u)
    c = db.get(m.CrCliente, f.cliente_id)
    email = (d.email or c.email or "").strip()
    if "@" not in email:
        raise HTTPException(422, "El cliente no tiene correo. Escriba uno.")
    try:
        cob.enviar(cfg, f, email)
    except cob.ErrorCobro as e:
        raise HTTPException(502, str(e))
    auditar(db, u, "cobro_factura_enviada", "cr_cliente", c.id, {"factura": f.id}, request)
    db.commit()
    return {"ok": True}


class CancelarFacturaIn(BaseModel):
    motivo: str


@router.post("/facturas/{fid}/cancelar")
def cancelar_factura(fid: int, d: CancelarFacturaIn, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    f, cfg = _factura(db, fid, u)
    if f.estado == "cancelada":
        raise HTTPException(409, "La factura ya está cancelada.")
    if d.motivo not in cob.MOTIVOS_CANCELACION:
        raise HTTPException(422, "Motivo de cancelación no válido.")
    try:
        estado = cob.cancelar(cfg, f, d.motivo)
    except cob.ErrorCobro as e:
        raise HTTPException(502, str(e))
    f.estado, f.motivo_cancelacion = estado, d.motivo
    if estado == "cancelada":
        f.cancelada_en = datetime.now(timezone.utc)
    auditar(db, u, "cobro_factura_cancelada", "cr_cliente", f.cliente_id, {"factura": f.id, "motivo": d.motivo}, request)
    db.commit()
    return _factura_dict(f)
