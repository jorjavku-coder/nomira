"""Cupones de descuento del panel de la plataforma.

Ver: superadministrador, soporte y ejecutivo comercial (para aplicarlos en cotizaciones).
Crear, editar, activar y suspender: superadministrador y ejecutivo comercial. El ejecutivo solo crea
cupones de porcentaje y hasta el descuento máximo autorizado en la configuración comercial."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, condecimal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..services import suscripciones as sus
from ..services.comercial import base as cm
from ..services.comercial import cupones as cp
from .plataforma import EJECUTIVO, _registrar, admin_plataforma

router = APIRouter(prefix="/api/plataforma/comercial/cupones", tags=["Plataforma — Cupones"])
ESTADOS_TEXTO = {"activo": "Activo", "suspendido": "Suspendido", "programado": "Programado", "vencido": "Vencido", "agotado": "Agotado"}


def gestor(a: m.AdminPlataforma = Depends(admin_plataforma)) -> m.AdminPlataforma:
    if a.rol not in ("superadministrador", EJECUTIVO):
        raise HTTPException(403, "Solo un superadministrador o un ejecutivo comercial administra cupones.")
    return a


class CuponIn(BaseModel):
    codigo: str = Field(min_length=3, max_length=40)
    descripcion: str | None = Field(None, max_length=300)
    tipo: Literal["porcentaje", "monto"] = "porcentaje"
    valor: condecimal(gt=0, max_digits=12, decimal_places=2)
    aplica_a: Literal["todo", "recurrente"] = "todo"
    inicia_en: date | None = None
    vence_en: date | None = None
    usos_maximos: int | None = Field(None, ge=1, le=100000)
    minimo: condecimal(ge=0, max_digits=12, decimal_places=2) | None = None


class EstadoIn(BaseModel):
    estado: Literal["activo", "suspendido"]


def _vista(c: m.CmCupon, admins: dict[int, str]) -> dict:
    est = cp.estado_vigencia(c, sus.hoy())
    return {"id": c.id, "codigo": c.codigo, "descripcion": c.descripcion, "tipo": c.tipo, "valor": cp.txt(c.valor),
            "aplica_a": c.aplica_a, "inicia_en": c.inicia_en.isoformat() if c.inicia_en else None,
            "vence_en": c.vence_en.isoformat() if c.vence_en else None, "usos_maximos": c.usos_maximos, "usos": c.usos,
            "minimo": cp.txt(c.minimo) if c.minimo is not None else None, "estado": c.estado, "vigencia": est,
            "vigencia_texto": ESTADOS_TEXTO[est], "creado_por": admins.get(c.creado_por_id), "creado_en": c.creado_en.isoformat()}


def _validar(db: Session, d: CuponIn, a: m.AdminPlataforma) -> str:
    codigo = cp.normalizar(d.codigo)
    if not cp.RE_CODIGO.match(codigo):
        raise HTTPException(422, "El código lleva de 3 a 40 letras o números, sin espacios ni acentos (se permiten - y _).")
    if d.tipo == "porcentaje" and d.valor > 100:
        raise HTTPException(422, "Un porcentaje no puede pasar de 100.")
    if d.inicia_en and d.vence_en and d.vence_en < d.inicia_en:
        raise HTTPException(422, "La fecha de vencimiento es anterior a la de inicio.")
    if a.rol == EJECUTIVO:
        maximo = cm.config(db).descuento_maximo_pct or Decimal("0")
        if d.tipo != "porcentaje":
            raise HTTPException(403, "Como ejecutivo comercial solo puede crear cupones de porcentaje.")
        if d.valor > maximo:
            raise HTTPException(403, f"El descuento supera el máximo autorizado ({maximo} %). Pídalo a un superadministrador.")
    return codigo


def _admins(db: Session) -> dict[int, str]:
    return dict(db.execute(select(m.AdminPlataforma.id, m.AdminPlataforma.nombre)).all())


def _cupon(db: Session, cid: int) -> m.CmCupon:
    c = db.get(m.CmCupon, cid)
    if not c:
        raise HTTPException(404, "No encontrado.")
    return c


@router.get("")
def listar(a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    admins = _admins(db)
    xs = db.scalars(select(m.CmCupon).order_by(m.CmCupon.estado, m.CmCupon.creado_en.desc())).all()
    return {"cupones": [_vista(c, admins) for c in xs], "puede_gestionar": a.rol in ("superadministrador", EJECUTIVO),
            "solo_porcentaje": a.rol == EJECUTIVO, "maximo_pct": cp.txt(cm.config(db).descuento_maximo_pct or Decimal("0"))}


@router.post("", status_code=201)
def crear(d: CuponIn, request: Request, a: m.AdminPlataforma = Depends(gestor), db: Session = Depends(get_db)):
    codigo = _validar(db, d, a)
    c = m.CmCupon(codigo=codigo, descripcion=(d.descripcion or "").strip() or None, tipo=d.tipo, valor=d.valor, aplica_a=d.aplica_a,
                  inicia_en=d.inicia_en, vence_en=d.vence_en, usos_maximos=d.usos_maximos, minimo=d.minimo, creado_por_id=a.id)
    db.add(c)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"Ya existe un cupón con el código {codigo}.")
    _registrar(db, a, "comercial_cupon_creado", request, entidad="cm_cupon", entidad_id=c.id,
               detalle={"codigo": codigo, "tipo": d.tipo, "valor": cp.txt(d.valor)})
    db.commit()
    return _vista(c, _admins(db))


@router.put("/{cid}")
def editar(cid: int, d: CuponIn, request: Request, a: m.AdminPlataforma = Depends(gestor), db: Session = Depends(get_db)):
    c = _cupon(db, cid)
    codigo = _validar(db, d, a)
    if codigo != c.codigo and c.usos:
        raise HTTPException(409, "Este cupón ya se usó: no se puede cambiar el código. Cree uno nuevo.")
    c.codigo, c.descripcion, c.tipo, c.valor, c.aplica_a = codigo, (d.descripcion or "").strip() or None, d.tipo, d.valor, d.aplica_a
    c.inicia_en, c.vence_en, c.usos_maximos, c.minimo, c.actualizado_en = d.inicia_en, d.vence_en, d.usos_maximos, d.minimo, cm.ahora()
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"Ya existe un cupón con el código {codigo}.")
    _registrar(db, a, "comercial_cupon_editado", request, entidad="cm_cupon", entidad_id=c.id, detalle={"codigo": codigo})
    db.commit()
    return _vista(c, _admins(db))


@router.post("/{cid}/estado")
def cambiar_estado(cid: int, d: EstadoIn, request: Request, a: m.AdminPlataforma = Depends(gestor), db: Session = Depends(get_db)):
    c = _cupon(db, cid)
    if a.rol == EJECUTIVO and d.estado == "activo" and (c.tipo != "porcentaje" or c.valor > (cm.config(db).descuento_maximo_pct or 0)):
        raise HTTPException(403, "Este cupón supera lo que un ejecutivo comercial puede autorizar. Pida a un superadministrador que lo active.")
    c.estado, c.actualizado_en = d.estado, cm.ahora()
    _registrar(db, a, f"comercial_cupon_{'activado' if d.estado == 'activo' else 'suspendido'}", request, entidad="cm_cupon",
               entidad_id=c.id, detalle={"codigo": c.codigo})
    db.commit()
    return _vista(c, _admins(db))


@router.delete("/{cid}")
def borrar(cid: int, request: Request, a: m.AdminPlataforma = Depends(gestor), db: Session = Depends(get_db)):
    c = _cupon(db, cid)
    if c.usos:
        raise HTTPException(409, "Este cupón ya se usó en pagos: suspéndalo en lugar de borrarlo para conservar el historial.")
    _registrar(db, a, "comercial_cupon_borrado", request, entidad="cm_cupon", entidad_id=c.id, detalle={"codigo": c.codigo})
    db.delete(c)
    db.commit()
    return {"ok": True}
