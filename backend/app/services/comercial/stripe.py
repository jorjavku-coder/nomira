"""Stripe Checkout para cotizaciones, en modo de prueba o real según STRIPE_MODO.

- La sesión de pago se crea en el servidor con el total calculado aquí; el navegador nunca manda importes.
- Nomira no recibe ni guarda datos de tarjeta: el cliente paga en la página de Stripe.
- La cotización solo se marca pagada con un webhook de firma válida, y cada evento se aplica una sola vez.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from decimal import Decimal

import httpx

from ...config import ajustes

API = "https://api.stripe.com/v1"
TOLERANCIA_S = 300


class StripeError(Exception):
    pass


def centavos(v: Decimal) -> int:
    return int((Decimal(v) * 100).to_integral_value())


def crear_sesion(*, folio: str, version: int, cotizacion_id: int, pago_id: int, total: Decimal, email: str, url_exito: str,
                 url_cancelar: str, idempotencia: str) -> dict:
    return crear_checkout(nombre=f"Nomira · Cotización {folio} (versión {version})", total=total, email=email, url_exito=url_exito,
                          url_cancelar=url_cancelar, idempotencia=idempotencia, referencia=folio,
                          metadata={"tipo": "cotizacion", "cotizacion_id": str(cotizacion_id), "version": str(version), "pago_id": str(pago_id),
                                    "folio": folio})


def crear_checkout(*, nombre: str, total: Decimal, email: str | None, url_exito: str, url_cancelar: str, idempotencia: str,
                   referencia: str, metadata: dict[str, str]) -> dict:
    """Sesión de Stripe Checkout de pago único en MXN por el total calculado en el servidor."""
    from .base import stripe_estado

    estado = stripe_estado()
    if not estado["conectado"]:
        raise StripeError(estado["motivo"] or "Pago en línea pendiente de configuración.")
    llave = ajustes().stripe_secret_key.strip()
    datos = {
        "mode": "payment", "client_reference_id": referencia[:200], "success_url": url_exito, "cancel_url": url_cancelar,
        "line_items[0][quantity]": "1", "line_items[0][price_data][currency]": "mxn",
        "line_items[0][price_data][unit_amount]": str(centavos(total)),
        "line_items[0][price_data][product_data][name]": nombre[:250],
        **{f"metadata[{k}]": v for k, v in metadata.items()},
    }
    if email:
        datos["customer_email"] = email
    try:
        r = httpx.post(f"{API}/checkout/sessions", data=datos, auth=(llave, ""), timeout=20, headers={"Idempotency-Key": idempotencia})
    except httpx.HTTPError as e:
        raise StripeError(f"No se pudo conectar con Stripe ({type(e).__name__}).") from e
    if r.status_code >= 300:
        try:
            detalle = r.json().get("error", {}).get("message") or r.text
        except ValueError:
            detalle = r.text
        raise StripeError(f"Stripe rechazó la solicitud ({r.status_code}): {detalle[:200]}")
    j = r.json()
    if not j.get("id") or not j.get("url"):
        raise StripeError("Stripe no devolvió la sesión de pago.")
    return {"id": j["id"], "url": j["url"]}


def firma_valida(cuerpo: bytes, encabezado: str | None, ahora: float | None = None) -> bool:
    secreto = ajustes().stripe_webhook_secret.strip()
    if not secreto or not encabezado:
        return False
    partes: dict[str, list[str]] = {}
    for p in encabezado.split(","):
        k, _, v = p.strip().partition("=")
        partes.setdefault(k, []).append(v)
    try:
        t = int(partes.get("t", ["0"])[0])
    except ValueError:
        return False
    if abs((ahora or time.time()) - t) > TOLERANCIA_S:
        return False
    esperado = hmac.new(secreto.encode(), f"{t}.".encode() + cuerpo, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(esperado, v) for v in partes.get("v1", []))
