"""Cupones de descuento (p. ej. BLACKDAY2026).

Un cupón se aplica a UNA cotización: lo captura quien la prepara en el panel o el cliente en su propuesta,
antes de aceptarla. El descuento se calcula sobre el subtotal (después del descuento autorizado, si lo hay),
antes de IVA. Los usos cuentan cuando la cotización queda PAGADA; el límite de usos se revisa al aplicarlo.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models as m

CENT = Decimal("0.01")
RE_CODIGO = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,39}$")


def normalizar(codigo: str | None) -> str:
    return re.sub(r"\s+", "", (codigo or "")).upper()


def txt(v: Decimal) -> str:
    return str(v.quantize(CENT))


def estado_vigencia(c: m.CmCupon, hoy: date) -> str:
    """activo | suspendido | programado | vencido | agotado"""
    if c.estado != "activo":
        return "suspendido"
    if c.inicia_en and hoy < c.inicia_en:
        return "programado"
    if c.vence_en and hoy > c.vence_en:
        return "vencido"
    if c.usos_maximos is not None and c.usos >= c.usos_maximos:
        return "agotado"
    return "activo"


MENSAJES = {"suspendido": "Ese cupón no está disponible.", "programado": "Ese cupón todavía no está vigente.",
            "vencido": "Ese cupón ya venció.", "agotado": "Ese cupón ya alcanzó su límite de usos."}


def buscar(db: Session, codigo: str, hoy: date) -> m.CmCupon:
    c = db.scalar(select(m.CmCupon).where(m.CmCupon.codigo == normalizar(codigo)))
    if not c:
        raise HTTPException(422, "Ese cupón no existe. Revise que esté bien escrito.")
    est = estado_vigencia(c, hoy)
    if est != "activo":
        raise HTTPException(422, MENSAJES[est])
    return c


def aplicar(calc: dict, c: m.CmCupon) -> dict:
    """Agrega el cupón a un desglose ya calculado (precios congelados) y recalcula base, IVA y total."""
    subtotal = Decimal(calc["subtotal"])
    manual = Decimal(calc["descuento"]["importe"]) if calc.get("descuento") else Decimal("0")
    disponible = subtotal - manual
    base = Decimal(calc["recurrente"]) if c.aplica_a == "recurrente" else subtotal
    base = min(base, disponible)
    if c.minimo is not None and subtotal < c.minimo:
        raise HTTPException(422, f"Ese cupón aplica a partir de ${c.minimo:,.2f} antes de IVA.")
    if c.tipo == "porcentaje":
        importe = (base * c.valor / 100).quantize(CENT, rounding=ROUND_HALF_UP)
        texto = f"{c.valor.normalize():f} %"
    else:
        importe = min(c.valor, base).quantize(CENT)
        texto = f"${c.valor:,.2f}"
    if importe <= 0:
        raise HTTPException(422, "Ese cupón no aplica a esta propuesta.")
    base_iva = disponible - importe
    iva = (base_iva * Decimal(calc["iva_pct"]) / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    nuevo = {**calc, "cupon": {"codigo": c.codigo, "tipo": c.tipo, "valor": txt(c.valor), "texto": texto,
                               "aplica_a": c.aplica_a, "importe": txt(importe)},
             "base_iva": txt(base_iva), "iva": txt(iva), "total": txt(base_iva + iva)}
    return nuevo


def sin_cupon(calc: dict) -> dict:
    """Quita el cupón de un desglose (para volver a aplicarlo o cambiarlo)."""
    if not calc.get("cupon"):
        return calc
    subtotal = Decimal(calc["subtotal"])
    manual = Decimal(calc["descuento"]["importe"]) if calc.get("descuento") else Decimal("0")
    base_iva = subtotal - manual
    iva = (base_iva * Decimal(calc["iva_pct"]) / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    x = {k: v for k, v in calc.items() if k != "cupon"}
    return {**x, "base_iva": txt(base_iva), "iva": txt(iva), "total": txt(base_iva + iva)}


def descuento_total(calc: dict) -> Decimal:
    d = Decimal(calc["descuento"]["importe"]) if calc.get("descuento") else Decimal("0")
    return d + (Decimal(calc["cupon"]["importe"]) if calc.get("cupon") else Decimal("0"))


def contar_uso(db: Session, calc: dict) -> None:
    """Se llama cuando una cotización queda pagada."""
    if not calc.get("cupon"):
        return
    c = db.scalar(select(m.CmCupon).where(m.CmCupon.codigo == calc["cupon"]["codigo"]).with_for_update())
    if c:
        c.usos += 1
