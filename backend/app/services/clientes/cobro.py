"""Cobro en línea y factura electrónica para los clientes DEL DESPACHO (no es el cobro de Nomira).

- Cada despacho conecta SU cuenta de Stripe (llave restringida o secreta) y SU cuenta de Facturapi (que ya tiene
  sus sellos digitales, CSD). Nomira guarda las llaves cifradas y solo muestra una pista (últimos 4 caracteres).
- Ligas de pago: Stripe Checkout en MXN por lo pendiente de un cargo. Stripe muestra los medios que el despacho
  tenga activos (tarjeta, OXXO, transferencia…). Nomira no ve ni guarda datos de tarjeta.
- El pago se confirma consultando la sesión en Stripe (al abrir el cliente y cada 15 minutos): si está pagada,
  se registra en Clientes y cobranza una sola vez.
- Facturas: CFDI 4.0 de ingreso, método PUE, timbrado por Facturapi a partir de un pago registrado. Las claves
  del SAT (producto, uso, retenciones) las define el despacho con su contador.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m
from ...config import ajustes
from ..afore.cifrado import cifrar, descifrar
from . import base as cb

STRIPE = "https://api.stripe.com/v1"
FACTURAPI = "https://www.facturapi.io/v2"
CENT = Decimal("0.01")
FORMAS_PAGO = {"transferencia": "03", "efectivo": "01", "tarjeta": "04", "cheque": "02", "deposito": "01", "en_linea": "04", "otro": "99"}
USOS = {"G03": "Gastos en general", "G01": "Adquisición de mercancías", "S01": "Sin efectos fiscales", "D01": "Honorarios médicos, dentales y hospitalarios",
        "P01": "Por definir"}
RETENCIONES = {"ninguna": "Sin retenciones", "honorarios": "ISR 10 % + IVA 10.6667 % (honorarios a personas morales)",
               "resico": "ISR 1.25 % (RESICO, a personas morales)"}
MOTIVOS_CANCELACION = {"02": "Comprobante emitido con errores sin relación", "03": "No se llevó a cabo la operación",
                       "04": "Operación nominativa relacionada en una factura global"}


class ErrorCobro(Exception):
    pass


def config(db: Session, org: int) -> m.CrConfigCobro:
    c = db.scalar(select(m.CrConfigCobro).where(m.CrConfigCobro.organizacion_id == org))
    if c is None:
        c = m.CrConfigCobro(organizacion_id=org)
        db.add(c)
        db.flush()
    return c


def pista(llave: str) -> str:
    return f"{llave[:8]}…{llave[-4:]}"


def es_prueba(llave_pista: str | None) -> bool:
    return bool(llave_pista) and ("_test_" in llave_pista)


def _error(r: httpx.Response, quien: str) -> ErrorCobro:
    try:
        j = r.json()
        msg = (j.get("error") or {}).get("message") if isinstance(j.get("error"), dict) else j.get("message")
    except ValueError:
        msg = None
    return ErrorCobro(f"{quien} rechazó la solicitud ({r.status_code}){': ' + str(msg)[:200] if msg else ''}.")


# ------------------------------------------------------------------ Stripe del despacho

def stripe_llave(c: m.CrConfigCobro) -> str:
    llave = descifrar(c.stripe_llave_cifrada)
    if not llave:
        raise ErrorCobro("Conecte primero su cuenta de Stripe en Clientes → Cobro y facturación.")
    return llave


def stripe_validar(llave: str, cliente: httpx.Client | None = None) -> None:
    if not re.fullmatch(r"(sk|rk)_(test|live)_[A-Za-z0-9]{10,}", llave):
        raise ErrorCobro("La llave de Stripe debe empezar con rk_live_, sk_live_, rk_test_ o sk_test_.")
    c = cliente or httpx
    try:
        r = c.get(f"{STRIPE}/checkout/sessions", params={"limit": 1}, auth=(llave, ""), timeout=15)
    except httpx.HTTPError as e:
        raise ErrorCobro(f"No se pudo conectar con Stripe ({type(e).__name__}).")
    if r.status_code in (401, 403):
        raise ErrorCobro("Stripe no aceptó la llave o le faltan permisos de «Checkout Sessions» (escritura).")
    if r.status_code >= 300:
        raise _error(r, "Stripe")


def crear_liga(db: Session, c: m.CrConfigCobro, cli: m.CrCliente, cargo: m.CrCargo | None, concepto: str, monto: Decimal, despacho: str,
               usuario_id: int, cliente_http: httpx.Client | None = None) -> m.CrLigaPago:
    llave = stripe_llave(c)
    if monto <= 0:
        raise ErrorCobro("No hay saldo pendiente que cobrar.")
    base = ajustes().url_publica.rstrip("/")
    datos = {"mode": "payment", "success_url": f"{base}/pago?resultado=ok", "cancel_url": f"{base}/pago?resultado=cancelado",
             "line_items[0][quantity]": "1", "line_items[0][price_data][currency]": "mxn",
             "line_items[0][price_data][unit_amount]": str(int((monto * 100).to_integral_value())),
             "line_items[0][price_data][product_data][name]": f"{concepto} · {despacho}"[:250],
             "metadata[origen]": "nomira_clientes", "metadata[cliente_id]": str(cli.id), "metadata[cargo_id]": str(cargo.id if cargo else ""),
             "client_reference_id": f"nomira-{cli.organizacion_id}-{cli.id}"}
    if cli.email:
        datos["customer_email"] = cli.email
    h = cliente_http or httpx
    try:
        r = h.post(f"{STRIPE}/checkout/sessions", data=datos, auth=(llave, ""), timeout=20)
    except httpx.HTTPError as e:
        raise ErrorCobro(f"No se pudo conectar con Stripe ({type(e).__name__}).")
    if r.status_code >= 300:
        raise _error(r, "Stripe")
    j = r.json()
    if not j.get("id") or not j.get("url"):
        raise ErrorCobro("Stripe no devolvió la liga de pago.")
    exp = datetime.fromtimestamp(j["expires_at"], timezone.utc) if j.get("expires_at") else None
    liga = m.CrLigaPago(organizacion_id=cli.organizacion_id, cliente_id=cli.id, cargo_id=cargo.id if cargo else None, concepto=concepto[:250],
                        monto=monto, stripe_sesion=j["id"], url=j["url"][:1000], expira_en=exp, creado_por_id=usuario_id)
    db.add(liga)
    db.flush()
    return liga


def sincronizar_liga(db: Session, liga: m.CrLigaPago, cliente_http: httpx.Client | None = None) -> bool:
    """Consulta la sesión en Stripe. Si está pagada registra el pago (una sola vez). Devuelve True si cambió."""
    if liga.estado != "pendiente":
        return False
    c = config(db, liga.organizacion_id)
    llave = descifrar(c.stripe_llave_cifrada)
    if not llave:
        return False
    h = cliente_http or httpx
    try:
        r = h.get(f"{STRIPE}/checkout/sessions/{liga.stripe_sesion}", auth=(llave, ""), timeout=15)
    except httpx.HTTPError:
        return False
    liga.revisada_en = datetime.now(timezone.utc)
    if r.status_code >= 300:
        return False
    j = r.json()
    if j.get("payment_status") in ("paid", "no_payment_required"):
        bloqueada = db.scalar(select(m.CrLigaPago).where(m.CrLigaPago.id == liga.id).with_for_update())
        if bloqueada.estado != "pendiente":
            return False
        cargo = db.get(m.CrCargo, liga.cargo_id) if liga.cargo_id else None
        p = m.CrPago(organizacion_id=liga.organizacion_id, cliente_id=liga.cliente_id, cargo_id=cargo.id if cargo and not cargo.cancelado_en else None,
                     folio=cb.siguiente_folio(db, liga.organizacion_id), monto=liga.monto, fecha=datetime.now(timezone.utc).date(),
                     metodo="en_linea", referencia=str(j.get("payment_intent") or liga.stripe_sesion)[:120], nota="Pagado con liga de pago (Stripe)")
        db.add(p)
        db.flush()
        liga.estado, liga.pago_id, liga.pagada_en = "pagada", p.id, datetime.now(timezone.utc)
        return True
    if j.get("status") == "expired":
        liga.estado = "vencida"
        return True
    return False


def sincronizar_pendientes(db: Session, org: int | None = None, cliente_id: int | None = None) -> int:
    q = select(m.CrLigaPago).where(m.CrLigaPago.estado == "pendiente", m.CrLigaPago.creado_en > datetime.now(timezone.utc) - timedelta(days=10))
    if org:
        q = q.where(m.CrLigaPago.organizacion_id == org)
    if cliente_id:
        q = q.where(m.CrLigaPago.cliente_id == cliente_id)
    n = 0
    for liga in db.scalars(q.limit(200)).all():
        if sincronizar_liga(db, liga):
            n += 1
    db.commit()
    return n


# ------------------------------------------------------------------ Facturapi del despacho

def facturapi_llave(c: m.CrConfigCobro) -> str:
    llave = descifrar(c.facturapi_llave_cifrada)
    if not llave:
        raise ErrorCobro("Conecte primero su cuenta de Facturapi en Clientes → Cobro y facturación.")
    return llave


def facturapi_validar(llave: str, cliente: httpx.Client | None = None) -> None:
    if not re.fullmatch(r"sk_(test|live)_[A-Za-z0-9]{10,}", llave):
        raise ErrorCobro("La llave de Facturapi debe empezar con sk_live_ o sk_test_.")
    h = cliente or httpx
    try:
        r = h.get(f"{FACTURAPI}/invoices", params={"limit": 1}, headers={"Authorization": f"Bearer {llave}"}, timeout=15)
    except httpx.HTTPError as e:
        raise ErrorCobro(f"No se pudo conectar con Facturapi ({type(e).__name__}).")
    if r.status_code in (401, 403):
        raise ErrorCobro("Facturapi no aceptó la llave.")
    if r.status_code >= 300:
        raise _error(r, "Facturapi")


REGIMENES = [("fines no lucrativos", "603"), ("general de ley", "601"), ("sueldos y salarios", "605"), ("arrendamiento", "606"),
              ("actividades empresariales y profesionales", "612"), ("sin obligaciones fiscales", "616"), ("incorporación fiscal", "621"),
              ("plataformas tecnológicas", "625"), ("simplificado de confianza", "626")]


def regimen(cli: m.CrCliente) -> str | None:
    """Clave del régimen fiscal del SAT: la escrita (601, 612…) o la que corresponde al nombre de la constancia."""
    t = (cli.regimen_fiscal or "").lower()
    x = re.search(r"\b(6\d{2})\b", t)
    if x:
        return x.group(1)
    return next((clave for nombre, clave in REGIMENES if nombre in t), None)


def desglose(total: Decimal, retenciones: str, persona_moral: bool) -> dict:
    """Del total cobrado al subtotal (base), IVA y retenciones. Las retenciones solo aplican a personas morales."""
    ret_isr, ret_iva = Decimal("0"), Decimal("0")
    if persona_moral and retenciones == "honorarios":
        ret_isr, ret_iva = Decimal("0.10"), Decimal("0.106667")
    elif persona_moral and retenciones == "resico":
        ret_isr = Decimal("0.0125")
    factor = Decimal("1") + Decimal("0.16") - ret_isr - ret_iva
    base = (total / factor).quantize(CENT, rounding=ROUND_HALF_UP)
    iva = (base * Decimal("0.16")).quantize(CENT, rounding=ROUND_HALF_UP)
    risr = (base * ret_isr).quantize(CENT, rounding=ROUND_HALF_UP)
    riva = (base * ret_iva).quantize(CENT, rounding=ROUND_HALF_UP)
    return {"subtotal": base, "iva": iva, "ret_isr": risr, "ret_iva": riva, "total": base + iva - risr - riva,
            "tasa_ret_isr": ret_isr, "tasa_ret_iva": ret_iva}


def faltantes(cli: m.CrCliente, c: m.CrConfigCobro) -> list[str]:
    r = []
    if not cli.rfc:
        r.append("RFC del cliente")
    if not regimen(cli):
        r.append("régimen fiscal del cliente (por ejemplo 601 o 612)")
    if not cli.codigo_postal:
        r.append("código postal fiscal del cliente")
    if not c.clave_producto:
        r.append("clave de producto o servicio del SAT (en Cobro y facturación)")
    return r


def timbrar(db: Session, c: m.CrConfigCobro, cli: m.CrCliente, pago: m.CrPago, concepto: str, uso: str, usuario_id: int,
            cliente_http: httpx.Client | None = None) -> m.CrFactura:
    llave = facturapi_llave(c)
    falta = faltantes(cli, c)
    if falta:
        raise ErrorCobro("Para facturar falta: " + ", ".join(falta) + ".")
    d = desglose(pago.monto, c.retenciones, cli.tipo == "moral")
    impuestos = [{"type": "IVA", "rate": 0.16}]
    if d["tasa_ret_isr"]:
        impuestos.append({"type": "ISR", "rate": float(d["tasa_ret_isr"]), "withholding": True})
    if d["tasa_ret_iva"]:
        impuestos.append({"type": "IVA", "rate": float(d["tasa_ret_iva"]), "withholding": True})
    cuerpo = {
        "customer": {"legal_name": cli.nombre, "tax_id": cli.rfc, "tax_system": regimen(cli), "email": cli.email or None,
                     "address": {"zip": cli.codigo_postal}},
        "items": [{"quantity": 1, "product": {"description": concepto[:1000], "product_key": c.clave_producto, "unit_key": c.clave_unidad or "E48",
                                               "price": float(d["subtotal"]), "tax_included": False, "taxes": impuestos}}],
        "payment_form": FORMAS_PAGO.get(pago.metodo, "99"), "payment_method": "PUE", "use": uso,
    }
    if not cuerpo["customer"]["email"]:
        cuerpo["customer"].pop("email")
    h = cliente_http or httpx
    try:
        r = h.post(f"{FACTURAPI}/invoices", json=cuerpo, headers={"Authorization": f"Bearer {llave}"}, timeout=40)
    except httpx.HTTPError as e:
        raise ErrorCobro(f"No se pudo conectar con Facturapi ({type(e).__name__}).")
    if r.status_code >= 300:
        raise _error(r, "Facturapi")
    j = r.json()
    serie = f"{j.get('series') or ''}{j.get('folio_number') or ''}" or None
    f = m.CrFactura(organizacion_id=cli.organizacion_id, cliente_id=cli.id, pago_id=pago.id, facturapi_id=str(j["id"]), uuid=j.get("uuid"),
                    serie_folio=serie, subtotal=d["subtotal"], total=Decimal(str(j.get("total", d["total"]))), uso=uso,
                    forma_pago=cuerpo["payment_form"], prueba=es_prueba(c.facturapi_pista), creado_por_id=usuario_id)
    db.add(f)
    db.flush()
    return f


def archivo(c: m.CrConfigCobro, f: m.CrFactura, formato: str, cliente_http: httpx.Client | None = None) -> bytes:
    h = cliente_http or httpx
    try:
        r = h.get(f"{FACTURAPI}/invoices/{f.facturapi_id}/{formato}", headers={"Authorization": f"Bearer {facturapi_llave(c)}"}, timeout=30)
    except httpx.HTTPError as e:
        raise ErrorCobro(f"No se pudo conectar con Facturapi ({type(e).__name__}).")
    if r.status_code >= 300:
        raise _error(r, "Facturapi")
    return r.content


def enviar(c: m.CrConfigCobro, f: m.CrFactura, email: str, cliente_http: httpx.Client | None = None) -> None:
    h = cliente_http or httpx
    try:
        r = h.post(f"{FACTURAPI}/invoices/{f.facturapi_id}/email", json={"email": email}, headers={"Authorization": f"Bearer {facturapi_llave(c)}"}, timeout=30)
    except httpx.HTTPError as e:
        raise ErrorCobro(f"No se pudo conectar con Facturapi ({type(e).__name__}).")
    if r.status_code >= 300:
        raise _error(r, "Facturapi")


def cancelar(c: m.CrConfigCobro, f: m.CrFactura, motivo: str, cliente_http: httpx.Client | None = None) -> str:
    """Devuelve «cancelada» o «en_cancelacion» (cuando el SAT pide que el receptor acepte la cancelación)."""
    h = cliente_http or httpx
    try:
        r = h.delete(f"{FACTURAPI}/invoices/{f.facturapi_id}", params={"motive": motivo}, headers={"Authorization": f"Bearer {facturapi_llave(c)}"}, timeout=40)
    except httpx.HTTPError as e:
        raise ErrorCobro(f"No se pudo conectar con Facturapi ({type(e).__name__}).")
    if r.status_code >= 300:
        raise _error(r, "Facturapi")
    try:
        j = r.json()
    except ValueError:
        j = {}
    return "cancelada" if j.get("status") == "canceled" else "en_cancelacion"


def guardar_llaves(c: m.CrConfigCobro, stripe: str | None, facturapi: str | None) -> None:
    if stripe is not None:
        c.stripe_llave_cifrada, c.stripe_pista = (cifrar(stripe), pista(stripe)) if stripe else (None, None)
    if facturapi is not None:
        c.facturapi_llave_cifrada, c.facturapi_pista = (cifrar(facturapi), pista(facturapi)) if facturapi else (None, None)
