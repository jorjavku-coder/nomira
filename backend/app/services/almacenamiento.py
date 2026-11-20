"""Espacio en disco por despacho y costo del almacenamiento del proveedor (Render).

- Cada despacho guarda sus archivos en STORAGE_DIR/<organizacion_id>/. Medimos esa carpeta.
- El espacio CONTRATADO sale de su asignación activa de Comercial (paquete + bloques adicionales).
- Medir una carpeta grande cuesta: se guarda el resultado unos minutos.
"""
from __future__ import annotations

import math
import os
import time
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes

GB = 1024 ** 3
_CACHE: dict[int, tuple[float, int]] = {}
_TTL = 300  # segundos


def carpeta(org_id: int) -> Path:
    return Path(ajustes().storage_dir) / str(org_id)


def _medir(ruta: Path) -> int:
    total = 0
    for raiz, _dirs, archivos in os.walk(ruta):
        for a in archivos:
            try:
                st = os.lstat(os.path.join(raiz, a))
            except OSError:
                continue
            total += st.st_size
    return total


def uso_bytes(org_id: int, fresco: bool = False) -> int:
    ahora = time.monotonic()
    x = _CACHE.get(org_id)
    if x and not fresco and ahora - x[0] < _TTL:
        return x[1]
    n = _medir(carpeta(org_id))
    _CACHE[org_id] = (ahora, n)
    return n


def olvidar(org_id: int) -> None:
    _CACHE.pop(org_id, None)


def asignacion_activa(db: Session, org_id: int) -> m.CmAsignacion | None:
    return db.scalar(select(m.CmAsignacion).where(m.CmAsignacion.organizacion_id == org_id, m.CmAsignacion.estado == "activa")
                     .order_by(m.CmAsignacion.inicio.desc(), m.CmAsignacion.id.desc()).limit(1))


def contratado_gb(db: Session, org_id: int) -> int | None:
    a = asignacion_activa(db, org_id)
    return a.almacenamiento_gb if a else None


# ------------------------------------------------------------------ costo del proveedor

def _d(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def precio_redondo(x: Decimal) -> Decimal:
    """Redondea hacia arriba a un precio comercial terminado en 9 (296.9 → 299)."""
    n = Decimal(math.ceil(x / 10) * 10 - 1)
    return n if n >= x else n + 10


def costos(db: Session, c: m.CmConfig) -> dict:
    usd, tc, margen = Decimal(c.costo_gb_usd), Decimal(c.tipo_cambio), Decimal(c.margen_almacenamiento_pct)
    gb_mxn = usd * tc
    bloque = db.scalar(select(m.CmPrecio).where(m.CmPrecio.clave == "almacenamiento"))
    gb_bloque = (bloque.unidad_gb if bloque else None) or 25
    costo_bloque = gb_mxn * gb_bloque
    sugerido = precio_redondo(costo_bloque * (1 + margen / 100))
    actual = Decimal(bloque.precio_mensual) if bloque else None
    paquetes = [{"id": p.id, "nombre": p.nombre, "gb": p.almacenamiento_gb, "costo_mxn": str(_d(gb_mxn * p.almacenamiento_gb)),
                 "pct_del_precio": float(_d(gb_mxn * p.almacenamiento_gb * 100 / p.precio_mensual)) if p.precio_mensual else None}
                for p in db.scalars(select(m.CmPaquete).where(m.CmPaquete.estado != "archivado").order_by(m.CmPaquete.orden, m.CmPaquete.id))]
    return {"costo_gb_mxn": str(_d(gb_mxn)),
            "bloque": {"id": bloque.id if bloque else None, "gb": gb_bloque, "costo_mxn": str(_d(costo_bloque)), "precio_sugerido": str(sugerido),
                       "precio_actual": str(_d(actual)) if actual is not None else None,
                       "margen_actual_pct": float(_d((actual / costo_bloque - 1) * 100)) if actual and costo_bloque else None},
            "paquetes": paquetes}


def resumen_disco(db: Session, c: m.CmConfig) -> dict:
    orgs = db.scalars(select(m.Organizacion).order_by(m.Organizacion.nombre)).all()
    filas, contratado, usado = [], 0, 0
    for o in orgs:
        gb = contratado_gb(db, o.id)
        u = uso_bytes(o.id)
        contratado += gb or 0
        usado += u
        filas.append({"id": o.id, "nombre": o.nombre, "contratado_gb": gb, "usado_mb": round(u / 1048576, 1),
                      "pct": round(u * 100 / (gb * GB), 1) if gb else None})
    usado_gb = usado / GB
    necesario = max(contratado, math.ceil(usado_gb * 1.2)) if (contratado or usado) else 0
    recomendado = max(c.disco_gb, int(math.ceil(necesario / 5) * 5)) if necesario else c.disco_gb
    gb_mxn = Decimal(c.costo_gb_usd) * Decimal(c.tipo_cambio)
    return {"disco_gb": c.disco_gb, "contratado_gb": contratado, "usado_gb": round(usado_gb, 2),
            "costo_disco_usd": str(_d(Decimal(c.costo_gb_usd) * c.disco_gb)), "costo_disco_mxn": str(_d(gb_mxn * c.disco_gb)),
            "recomendado_gb": recomendado, "ampliar": recomendado > c.disco_gb,
            "costo_recomendado_usd": str(_d(Decimal(c.costo_gb_usd) * recomendado)), "organizaciones": filas}
