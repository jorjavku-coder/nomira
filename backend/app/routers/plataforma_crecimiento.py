"""Panel de la plataforma: crecimiento (reglas de juegos y referidos, ruleta, tienda, trivia y red de despachos).
Solo conteos y nombres de despachos: nunca los datos de las personas que pidieron un abogado."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..services.crecimiento import base, juegos, red
from .plataforma import _registrar, admin_plataforma, superadmin

router = APIRouter(prefix="/api/plataforma/crecimiento", tags=["Plataforma — Crecimiento"])


def _cfg(c: m.CxConfig) -> dict:
    return {k: getattr(c, k) for k in ("juegos_activos", "ruleta_activa", "ruleta_permiso", "puntos_por_acierto", "preguntas_por_dia",
                                       "tope_puntos_dia_org", "tope_meses_anual", "referidos_activos", "meses_referido",
                                       "tope_referidos_anual", "casos_activos")}


def _premio(p: m.CxPremio) -> dict:
    return {k: getattr(p, k) for k in ("id", "lugar", "etiqueta", "tipo", "valor", "peso", "costo", "tope_mensual", "orden", "activo")}


def _pregunta(p: m.CxPregunta, n: int = 0, ok: int = 0) -> dict:
    return {"id": p.id, "materia": p.materia, "texto": p.texto, "opciones": p.opciones, "correcta": p.correcta, "explicacion": p.explicacion,
            "activa": p.activa, "de_fabrica": bool(p.clave), "respuestas": n, "aciertos": ok}


@router.get("")
def resumen(dias: int = 30, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    c = base.config(db)
    desde = datetime.combine(base.hoy() - timedelta(days=dias), datetime.min.time())
    cuenta = lambda modelo, *cond: int(db.scalar(select(func.count()).select_from(modelo).where(*cond)) or 0)
    stats: dict[int, tuple[int, int]] = {}
    for pid, correcta, n in db.execute(select(m.CxRespuesta.pregunta_id, m.CxRespuesta.correcta, func.count())
                                       .group_by(m.CxRespuesta.pregunta_id, m.CxRespuesta.correcta)).all():
        t, ok = stats.get(pid, (0, 0))
        stats[pid] = (t + n, ok + (n if correcta else 0))
    nombres = dict(db.execute(select(m.Organizacion.id, m.Organizacion.nombre)).all())
    redes = db.scalars(select(m.CxRed).order_by(m.CxRed.id)).all()
    por_estado = dict(db.execute(select(m.CxCaso.estado_mx, func.count()).where(m.CxCaso.creado_en >= desde).group_by(m.CxCaso.estado_mx)).all())
    meses = lambda origen: int(db.scalar(select(func.coalesce(func.sum(m.CxRecompensa.valor), 0)).where(
        m.CxRecompensa.tipo == "meses", m.CxRecompensa.origen.in_(origen), m.CxRecompensa.creado_en >= desde)) or 0)
    datos = {
        "dias": dias, "config": _cfg(c), "puede_editar": a.rol == "superadministrador",
        "cifras": {
            "jugadores": int(db.scalar(select(func.count(func.distinct(m.CxRespuesta.usuario_id))).where(m.CxRespuesta.creado_en >= desde)) or 0),
            "respuestas": cuenta(m.CxRespuesta, m.CxRespuesta.creado_en >= desde),
            "giros": cuenta(m.CxGiro, m.CxGiro.creado_en >= desde),
            "descuentos": cuenta(m.CxRecompensa, m.CxRecompensa.tipo == "descuento", m.CxRecompensa.creado_en >= desde),
            "meses_juegos": meses(("ruleta", "tienda")), "meses_referidos": meses(("referido", "invitado")),
            "referidos": cuenta(m.CxReferido, m.CxReferido.creado_en >= desde),
            "referidos_pagaron": cuenta(m.CxReferido, m.CxReferido.estado == "premiado", m.CxReferido.creado_en >= desde),
            "casos": cuenta(m.CxCaso, m.CxCaso.creado_en >= desde), "despachos_red": sum(1 for r in redes if r.activo),
        },
        "ruleta": [_premio(p) for p in db.scalars(select(m.CxPremio).where(m.CxPremio.lugar == "ruleta").order_by(m.CxPremio.orden, m.CxPremio.id)).all()],
        "probabilidades": juegos.probabilidades(db),
        "tienda": [_premio(p) for p in db.scalars(select(m.CxPremio).where(m.CxPremio.lugar == "tienda").order_by(m.CxPremio.costo, m.CxPremio.id)).all()],
        "preguntas": [_pregunta(p, *stats.get(p.id, (0, 0))) for p in db.scalars(select(m.CxPregunta).order_by(m.CxPregunta.materia, m.CxPregunta.id)).all()],
        "red": [{"despacho": nombres.get(r.organizacion_id, "—"), "activo": r.activo, "estados": r.estados, "tope_mensual": r.tope_mensual,
                 "cumple": all(red.requisitos(db, r.organizacion_id).values()),
                 "recibidos": cuenta(m.CxCaso, m.CxCaso.organizacion_id == r.organizacion_id, m.CxCaso.creado_en >= desde)} for r in redes],
        "casos_por_estado": [{"estado": red.ESTADOS_MX.get(k, k), "casos": v} for k, v in sorted(por_estado.items(), key=lambda x: -x[1])],
        "referidos": [{"invita": nombres.get(r.referidor_id, "—"), "invitado": nombres.get(r.referido_id, "—"), "estado": r.estado,
                       "desde": r.creado_en.date().isoformat()} for r in db.scalars(select(m.CxReferido).order_by(m.CxReferido.id.desc()).limit(100)).all()],
    }
    db.commit()
    return datos


class ConfigIn(BaseModel):
    juegos_activos: bool
    ruleta_activa: bool
    ruleta_permiso: str | None = Field(None, max_length=120)
    puntos_por_acierto: int = Field(ge=0, le=1000)
    preguntas_por_dia: int = Field(ge=1, le=10)
    tope_puntos_dia_org: int = Field(ge=0, le=10000)
    tope_meses_anual: int = Field(ge=0, le=24)
    referidos_activos: bool
    meses_referido: int = Field(ge=0, le=12)
    tope_referidos_anual: int = Field(ge=0, le=60)
    casos_activos: bool


@router.put("/config")
def guardar_config(d: ConfigIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    c = base.config(db)
    antes = _cfg(c)
    for k, v in d.model_dump().items():
        setattr(c, k, (v or "").strip() or None if k == "ruleta_permiso" else v)
    _registrar(db, a, "crecimiento_config", request, detalle={k: str(v) for k, v in _cfg(c).items() if antes.get(k) != v})
    db.commit()
    return _cfg(c)


class PremioIn(BaseModel):
    lugar: Literal["ruleta", "tienda"]
    etiqueta: str = Field(min_length=2, max_length=60)
    tipo: Literal["puntos", "descuento", "meses"]
    valor: int = Field(ge=1, le=1000)
    peso: int = Field(0, ge=0, le=100000)
    costo: int = Field(0, ge=0, le=1000000)
    tope_mensual: int | None = Field(None, ge=0, le=100000)
    orden: int = 0
    activo: bool = True


def _validar_premio(d: PremioIn) -> None:
    if d.tipo == "descuento" and d.valor > 50:
        raise HTTPException(422, "Un descuento de premio no puede pasar de 50 %.")
    if d.tipo == "meses" and d.valor > 12:
        raise HTTPException(422, "Un premio no puede dar más de 12 meses.")
    if d.lugar == "tienda" and (d.tipo == "puntos" or d.costo < 1):
        raise HTTPException(422, "En la tienda se cambian puntos por descuentos o meses, con un costo mayor a cero.")


@router.post("/premios", status_code=201)
def crear_premio(d: PremioIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    _validar_premio(d)
    p = m.CxPremio(**d.model_dump())
    db.add(p)
    db.flush()
    _registrar(db, a, "crecimiento_premio_creado", request, entidad="cx_premio", entidad_id=p.id, detalle={"etiqueta": p.etiqueta, "lugar": p.lugar})
    db.commit()
    return _premio(p)


@router.put("/premios/{pid}")
def editar_premio(pid: int, d: PremioIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    p = db.get(m.CxPremio, pid)
    if not p:
        raise HTTPException(404, "No encontrado.")
    _validar_premio(d)
    for k, v in d.model_dump().items():
        setattr(p, k, v)
    _registrar(db, a, "crecimiento_premio_editado", request, entidad="cx_premio", entidad_id=p.id, detalle={"etiqueta": p.etiqueta})
    db.commit()
    return _premio(p)


class PreguntaIn(BaseModel):
    materia: str = Field(min_length=2, max_length=40)
    texto: str = Field(min_length=10, max_length=400)
    opciones: list[str] = Field(min_length=2, max_length=6)
    correcta: int = Field(ge=0, le=5)
    explicacion: str = Field(min_length=10, max_length=800)
    activa: bool = True


def _validar_pregunta(d: PreguntaIn) -> list[str]:
    ops = [o.strip()[:200] for o in d.opciones]
    if any(not o for o in ops) or len(set(ops)) != len(ops):
        raise HTTPException(422, "Las opciones no pueden ir vacías ni repetidas.")
    if d.correcta >= len(ops):
        raise HTTPException(422, "Marque cuál es la opción correcta.")
    return ops


@router.post("/preguntas", status_code=201)
def crear_pregunta(d: PreguntaIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    p = m.CxPregunta(materia=d.materia.strip(), texto=d.texto.strip(), opciones=_validar_pregunta(d), correcta=d.correcta,
                     explicacion=d.explicacion.strip(), activa=d.activa)
    db.add(p)
    db.flush()
    _registrar(db, a, "crecimiento_pregunta_creada", request, entidad="cx_pregunta", entidad_id=p.id)
    db.commit()
    return _pregunta(p)


@router.put("/preguntas/{pid}")
def editar_pregunta(pid: int, d: PreguntaIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    p = db.get(m.CxPregunta, pid)
    if not p:
        raise HTTPException(404, "No encontrada.")
    p.materia, p.texto, p.opciones, p.correcta, p.explicacion, p.activa = (d.materia.strip(), d.texto.strip(), _validar_pregunta(d), d.correcta,
                                                                          d.explicacion.strip(), d.activa)
    _registrar(db, a, "crecimiento_pregunta_editada", request, entidad="cx_pregunta", entidad_id=p.id)
    db.commit()
    return _pregunta(p)
