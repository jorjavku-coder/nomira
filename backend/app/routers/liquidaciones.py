"""Liquidaciones LFT: calculadora de finiquito, indemnización, salarios caídos y horas extra, con cálculos guardados
por persona trabajadora, ligados a un asunto de la Agenda y a un cliente, y la propuesta de convenio.

Forma parte del módulo «Nómina y prestaciones». Leer: cualquier rol. Guardar: administrador y analista."""
from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, condecimal
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import auditar, puede_editar, usuario_actual
from ..services.agenda.base import hoy
from ..services.liquidacion import motor

router = APIRouter(prefix="/api/liquidaciones", tags=["Liquidaciones LFT"])
Monto = condecimal(ge=0, max_digits=14, decimal_places=2)
Dias = condecimal(ge=0, le=99999, max_digits=8, decimal_places=2)


class PeriodoExtraIn(BaseModel):
    desde: date
    hasta: date
    horas_semana: condecimal(gt=0, le=168, max_digits=6, decimal_places=2)


class OtroIn(BaseModel):
    concepto: str = Field(min_length=1, max_length=120)
    importe: Monto


class DatosIn(BaseModel):
    fecha_ingreso: date
    fecha_baja: date
    causa: Literal["renuncia", "mutuo_acuerdo", "despido_justificado", "despido_injustificado", "rescision_trabajador", "fallecimiento"]
    salario_diario: condecimal(gt=0, max_digits=12, decimal_places=2)
    fecha_calculo: date | None = None
    salario_integrado: Monto | None = None
    otras_prestaciones_diarias: Monto = Decimal("0")
    zona: Literal["general", "frontera"] = "general"
    salario_minimo: Monto | None = None
    aguinaldo_dias: condecimal(ge=15, le=365, max_digits=6, decimal_places=2) = Decimal("15")
    prima_vacacional_pct: condecimal(ge=25, le=100, max_digits=5, decimal_places=2) = Decimal("25")
    dias_pendientes_pago: Dias = Decimal("0")
    incluir_aguinaldo: bool = True
    vacaciones_anteriores_dias: Dias = Decimal("0")
    vacaciones_tomadas_actual: Dias = Decimal("0")
    incluir_20_dias: bool | None = None
    incluir_salarios_caidos: bool | None = None
    tipo_jornada: Literal["diurna", "mixta", "nocturna"] = "diurna"
    horas_extra: list[PeriodoExtraIn] = Field(default_factory=list, max_length=40)
    otros: list[OtroIn] = Field(default_factory=list, max_length=30)


class CalculoIn(BaseModel):
    titulo: str | None = Field(default=None, max_length=200)
    trabajador: str = Field(min_length=1, max_length=200)
    patron: str | None = Field(default=None, max_length=200)
    ag_asunto_id: int | None = None
    cr_cliente_id: int | None = None
    datos: DatosIn
    propuesta: Monto | None = None
    autorizado: Monto | None = None
    notas: str | None = Field(default=None, max_length=4000)


def _txt(v: str | None, n: int) -> str | None:
    v = re.sub(r"\s+", " ", v or "").strip()
    return v[:n] or None


def _motor(d: DatosIn) -> motor.Datos:
    x = d.model_dump()
    x["horas_extra"] = [motor.PeriodoExtra(**p) for p in x["horas_extra"]]
    x["otros"] = [motor.OtroConcepto(concepto=_txt(o["concepto"], 120) or "Concepto", importe=o["importe"]) for o in x["otros"]]
    return motor.Datos(**x)


def _calcular(d: DatosIn) -> dict:
    try:
        return motor.calcular(_motor(d), hoy())
    except motor.ErrorDatos as e:
        raise HTTPException(422, str(e))


def _calc(db: Session, cid: int, u: m.Usuario) -> m.LqCalculo:
    c = db.get(m.LqCalculo, cid)
    if not c or c.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrado.")
    return c


def _vinculos(db: Session, d: CalculoIn, u: m.Usuario) -> None:
    if d.ag_asunto_id:
        a = db.get(m.AgAsunto, d.ag_asunto_id)
        if not a or a.organizacion_id != u.organizacion_id:
            raise HTTPException(422, "El asunto no existe.")
    if d.cr_cliente_id:
        c = db.get(m.CrCliente, d.cr_cliente_id)
        if not c or c.organizacion_id != u.organizacion_id:
            raise HTTPException(422, "El cliente no existe.")


def _pct(parte: Decimal | None, total: Decimal) -> str | None:
    if parte is None or not total:
        return None
    return str((parte * 100 / total).quantize(Decimal("0.1")))


def _vista(db: Session, c: m.LqCalculo, completo: bool = False) -> dict:
    a = db.get(m.AgAsunto, c.ag_asunto_id) if c.ag_asunto_id else None
    cl = db.get(m.CrCliente, c.cr_cliente_id) if c.cr_cliente_id else None
    x = {"id": c.id, "titulo": c.titulo, "trabajador": c.trabajador, "patron": c.patron, "causa": c.causa,
         "causa_nombre": motor.CAUSAS.get(c.causa, c.causa), "total": motor.txt(c.total),
         "propuesta": motor.txt(c.propuesta), "autorizado": motor.txt(c.autorizado),
         "propuesta_pct": _pct(c.propuesta, c.total), "autorizado_pct": _pct(c.autorizado, c.total),
         "asunto": {"id": a.id, "titulo": a.titulo, "numero": a.numero} if a else None,
         "cliente": {"id": cl.id, "nombre": cl.nombre} if cl else None,
         "creado_en": c.creado_en.isoformat(), "actualizado_en": (c.actualizado_en or c.creado_en).isoformat()}
    if completo:
        x.update({"datos": c.datos, "resultado": c.resultado, "notas": c.notas, "ag_asunto_id": c.ag_asunto_id, "cr_cliente_id": c.cr_cliente_id})
    return x


@router.get("/tablas")
def tablas(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    asuntos = db.scalars(select(m.AgAsunto).where(m.AgAsunto.organizacion_id == u.organizacion_id, m.AgAsunto.estado == "activo")
                         .order_by(m.AgAsunto.titulo).limit(500))
    return {**motor.tablas(), "hoy": hoy().isoformat(), "puede_editar": u.rol in ("administrador", "analista"),
            "asuntos": [{"id": a.id, "titulo": a.titulo, "numero": a.numero} for a in asuntos]}


@router.post("/calcular")
def calcular(d: DatosIn, u: m.Usuario = Depends(usuario_actual)):
    """Vista previa: calcula sin guardar."""
    return _calcular(d)


@router.get("")
def listar(q: str | None = None, asunto: int | None = None, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    st = select(m.LqCalculo).where(m.LqCalculo.organizacion_id == u.organizacion_id)
    if asunto:
        st = st.where(m.LqCalculo.ag_asunto_id == asunto)
    if q and q.strip():
        t = f"%{q.strip()[:80]}%"
        st = st.where(or_(m.LqCalculo.titulo.ilike(t), m.LqCalculo.trabajador.ilike(t), m.LqCalculo.patron.ilike(t)))
    xs = db.scalars(st.order_by(m.LqCalculo.actualizado_en.desc().nulls_last(), m.LqCalculo.id.desc()).limit(300)).all()
    return {"calculos": [_vista(db, c) for c in xs]}


@router.get("/exposicion")
def exposicion(asunto: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Exposición económica de un asunto: suma de los cálculos ligados (una fila por persona trabajadora)."""
    a = db.get(m.AgAsunto, asunto)
    if not a or a.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrado.")
    xs = db.scalars(select(m.LqCalculo).where(m.LqCalculo.ag_asunto_id == asunto).order_by(m.LqCalculo.trabajador)).all()
    total = sum((c.total for c in xs), Decimal("0"))
    prop = sum((c.propuesta or Decimal("0") for c in xs), Decimal("0"))
    aut = sum((c.autorizado or Decimal("0") for c in xs), Decimal("0"))
    return {"calculos": [_vista(db, c) for c in xs], "total": motor.txt(total),
            "propuesta": motor.txt(prop) if any(c.propuesta is not None for c in xs) else None,
            "autorizado": motor.txt(aut) if any(c.autorizado is not None for c in xs) else None}


@router.post("", status_code=201)
def crear(d: CalculoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    _vinculos(db, d, u)
    r = _calcular(d.datos)
    trabajador = _txt(d.trabajador, 200)
    if not trabajador:
        raise HTTPException(422, "Capture el nombre de la persona trabajadora.")
    c = m.LqCalculo(organizacion_id=u.organizacion_id, titulo=_txt(d.titulo, 200) or f"{r['causa_nombre']} — {trabajador}",
                    trabajador=trabajador, patron=_txt(d.patron, 200), ag_asunto_id=d.ag_asunto_id, cr_cliente_id=d.cr_cliente_id,
                    causa=d.datos.causa, datos=d.datos.model_dump(mode="json"), resultado=r, total=Decimal(r["total"]),
                    propuesta=d.propuesta, autorizado=d.autorizado, notas=(d.notas or "").strip() or None, creado_por_id=u.id)
    db.add(c)
    db.flush()
    auditar(db, u, "liquidacion.crear", "lq_calculo", c.id, {"causa": c.causa}, request)
    db.commit()
    return _vista(db, c, True)


@router.get("/{cid}")
def ver(cid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    org = db.get(m.Organizacion, u.organizacion_id)
    return {**_vista(db, _calc(db, cid, u), True),
            "despacho": {"nombre": org.nombre, "tiene_logo": org.logo_actualizado is not None}}


@router.put("/{cid}")
def actualizar(cid: int, d: CalculoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _calc(db, cid, u)
    _vinculos(db, d, u)
    r = _calcular(d.datos)
    trabajador = _txt(d.trabajador, 200)
    if not trabajador:
        raise HTTPException(422, "Capture el nombre de la persona trabajadora.")
    c.titulo = _txt(d.titulo, 200) or f"{r['causa_nombre']} — {trabajador}"
    c.trabajador, c.patron = trabajador, _txt(d.patron, 200)
    c.ag_asunto_id, c.cr_cliente_id = d.ag_asunto_id, d.cr_cliente_id
    c.causa, c.datos, c.resultado, c.total = d.datos.causa, d.datos.model_dump(mode="json"), r, Decimal(r["total"])
    c.propuesta, c.autorizado, c.notas = d.propuesta, d.autorizado, (d.notas or "").strip() or None
    c.actualizado_en = datetime.now(timezone.utc)
    auditar(db, u, "liquidacion.actualizar", "lq_calculo", c.id, {"causa": c.causa}, request)
    db.commit()
    return _vista(db, c, True)


@router.delete("/{cid}")
def borrar(cid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _calc(db, cid, u)
    auditar(db, u, "liquidacion.borrar", "lq_calculo", c.id, {}, request)
    db.delete(c)
    db.commit()
    return {"ok": True}


@router.get("/{cid}/csv")
def exportar(cid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = _calc(db, cid, u)
    r = c.resultado
    f = io.StringIO()
    w = csv.writer(f)
    w.writerow(["Cálculo", c.titulo])
    w.writerow(["Persona trabajadora", c.trabajador])
    w.writerow(["Patrón", c.patron or ""])
    w.writerow(["Causa", r["causa_nombre"]])
    w.writerow(["Salario diario", r["salarios"]["diario"]])
    w.writerow(["Salario diario integrado", r["salarios"]["integrado"]])
    w.writerow(["Antigüedad (años)", r["antiguedad"]["anios"]])
    w.writerow([])
    w.writerow(["Sección", "Concepto", "Importe", "Operación", "Fundamento"])
    for s in r["secciones"]:
        for x in s["conceptos"]:
            w.writerow([s["titulo"], x["concepto"], x["importe"], x["operacion"], x["fundamento"]])
    w.writerow([])
    w.writerow(["", "TOTAL", r["total"]])
    if c.propuesta is not None:
        w.writerow(["", "Propuesta de convenio", motor.txt(c.propuesta)])
    if c.autorizado is not None:
        w.writerow(["", "Monto autorizado por el cliente", motor.txt(c.autorizado)])
    nombre = re.sub(r"[^A-Za-z0-9_-]+", "-", c.trabajador)[:40].strip("-") or "calculo"
    return Response("﻿" + f.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="liquidacion-{nombre}.csv"'})
