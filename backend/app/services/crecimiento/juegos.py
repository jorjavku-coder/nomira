"""Trivia del día, ruleta semanal y tienda de puntos."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ... import models as m
from . import base


# ---------------------------------------------------------------- trivia

def _orden(pid: int, uid: int, dia) -> str:
    return hashlib.sha256(f"{pid}:{uid}:{dia.isoformat()}".encode()).hexdigest()


def trivia_hoy(db: Session, u: m.Usuario) -> list[dict]:
    """Las preguntas del día de este usuario (estables durante el día) y las que ya contestó."""
    c = base.config(db)
    dia = base.hoy()
    hechas = {r.pregunta_id: r for r in db.scalars(select(m.CxRespuesta).where(m.CxRespuesta.usuario_id == u.id)).all()}
    de_hoy = [pid for pid, r in hechas.items() if r.dia == dia]
    faltan = max(0, c.preguntas_por_dia - len(de_hoy))
    libres = [p for p in db.scalars(select(m.CxPregunta).where(m.CxPregunta.activa.is_(True))).all() if p.id not in hechas]
    libres.sort(key=lambda p: _orden(p.id, u.id, dia))
    ids = de_hoy + [p.id for p in libres[:faltan]]
    preguntas = {p.id: p for p in db.scalars(select(m.CxPregunta).where(m.CxPregunta.id.in_(ids))).all()} if ids else {}
    salida = []
    for pid in ids:
        p = preguntas.get(pid)
        if not p:
            continue
        x = {"id": p.id, "materia": p.materia, "texto": p.texto, "opciones": p.opciones}
        r = hechas.get(pid)
        if r:
            x["respuesta"] = {"elegida": r.elegida, "correcta": r.correcta, "opcion_correcta": p.correcta, "explicacion": p.explicacion}
        salida.append(x)
    return salida


def responder(db: Session, u: m.Usuario, pregunta_id: int, elegida: int) -> dict:
    c = base.config(db)
    if not c.juegos_activos:
        raise HTTPException(409, "Los juegos están en pausa por ahora.")
    if pregunta_id not in [x["id"] for x in trivia_hoy(db, u)]:
        raise HTTPException(409, "Esa pregunta no es de su trivia de hoy.")
    p = db.get(m.CxPregunta, pregunta_id)
    if db.scalar(select(m.CxRespuesta.id).where(m.CxRespuesta.usuario_id == u.id, m.CxRespuesta.pregunta_id == p.id)):
        raise HTTPException(409, "Ya contestó esta pregunta.")
    if not 0 <= elegida < len(p.opciones):
        raise HTTPException(422, "Opción no válida.")
    base.candado(db, u.organizacion_id)
    ok = elegida == p.correcta
    db.add(m.CxRespuesta(usuario_id=u.id, organizacion_id=u.organizacion_id, pregunta_id=p.id, elegida=elegida, correcta=ok, dia=base.hoy()))
    ganados = 0
    if ok:
        ganados = max(0, min(c.puntos_por_acierto, c.tope_puntos_dia_org - base.puntos_hoy(db, u.organizacion_id)))
        if ganados:
            base.mover(db, u.organizacion_id, u.id, "trivia", ganados, f"Trivia: {p.materia}")
    db.flush()
    return {"correcta": ok, "opcion_correcta": p.correcta, "explicacion": p.explicacion, "puntos": ganados,
            "tope_alcanzado": ok and ganados < c.puntos_por_acierto}


# ---------------------------------------------------------------- ruleta

CONSOLACION = 20  # puntos cuando ninguna casilla puede salir (topes alcanzados)


def semana(d=None) -> str:
    y, w, _ = (d or base.hoy()).isocalendar()
    return f"{y}-W{w:02d}"


def casillas(db: Session) -> list[m.CxPremio]:
    return list(db.scalars(select(m.CxPremio).where(m.CxPremio.lugar == "ruleta", m.CxPremio.activo.is_(True), m.CxPremio.peso > 0)
                           .order_by(m.CxPremio.orden, m.CxPremio.id)).all())


def probabilidades(db: Session) -> list[dict]:
    xs = casillas(db)
    total = sum(x.peso for x in xs) or 1
    return [{"id": x.id, "etiqueta": x.etiqueta, "tipo": x.tipo, "valor": x.valor, "probabilidad": round(100 * x.peso / total, 2)} for x in xs]


def giro_de_semana(db: Session, org_id: int) -> m.CxGiro | None:
    return db.scalar(select(m.CxGiro).where(m.CxGiro.organizacion_id == org_id, m.CxGiro.semana == semana()))


def _salidas_del_mes(db: Session, premio_id: int) -> int:
    h = base.hoy()
    desde = datetime(h.year, h.month, 1)
    return int(db.scalar(select(func.count()).select_from(m.CxGiro).where(m.CxGiro.premio_id == premio_id, m.CxGiro.creado_en >= desde)) or 0)


def girar(db: Session, u: m.Usuario) -> dict:
    c = base.config(db)
    if not (c.juegos_activos and c.ruleta_activa):
        raise HTTPException(409, "La ruleta no está disponible por ahora.")
    base.candado(db, u.organizacion_id)
    if giro_de_semana(db, u.organizacion_id):
        raise HTTPException(409, "Su despacho ya giró la ruleta esta semana. Vuelva el lunes.")
    xs = casillas(db)
    if not xs:
        raise HTTPException(409, "La ruleta no tiene premios configurados.")
    sin_meses = base.meses_del_anio(db, u.organizacion_id, ("ruleta", "tienda")) >= c.tope_meses_anual
    posibles = [x for x in xs if not (x.tope_mensual is not None and _salidas_del_mes(db, x.id) >= x.tope_mensual)
                and not (x.tipo == "meses" and (sin_meses or base.meses_del_anio(db, u.organizacion_id, ("ruleta", "tienda")) + x.valor > c.tope_meses_anual))]
    if not posibles:  # todo agotado o fuera de tope: premio de consolación fijo
        premio = m.CxPremio(id=None, lugar="ruleta", etiqueta=f"{CONSOLACION} puntos", tipo="puntos", valor=CONSOLACION)
    else:
        n = secrets.randbelow(sum(x.peso for x in posibles))
        for x in posibles:
            n -= x.peso
            if n < 0:
                premio = x
                break
    db.add(m.CxGiro(organizacion_id=u.organizacion_id, usuario_id=u.id, semana=semana(), premio_id=premio.id, etiqueta=premio.etiqueta))
    recompensa = _entregar(db, u, premio, "ruleta", f"Ruleta: {premio.etiqueta}")
    db.flush()
    return {"premio": {"id": premio.id, "etiqueta": premio.etiqueta, "tipo": premio.tipo, "valor": premio.valor},
            "recompensa": base.vista_recompensa(db, recompensa) if recompensa else None}


def _entregar(db: Session, u: m.Usuario, premio: m.CxPremio, origen: str, descripcion: str) -> m.CxRecompensa | None:
    if premio.tipo == "puntos":
        base.mover(db, u.organizacion_id, u.id, origen, premio.valor, descripcion)
        return None
    return base.otorgar(db, u.organizacion_id, origen, premio.tipo, premio.valor, descripcion)


# ---------------------------------------------------------------- tienda

def tienda(db: Session) -> list[m.CxPremio]:
    return list(db.scalars(select(m.CxPremio).where(m.CxPremio.lugar == "tienda", m.CxPremio.activo.is_(True))
                           .order_by(m.CxPremio.costo, m.CxPremio.id)).all())


def canjear(db: Session, u: m.Usuario, premio_id: int) -> m.CxRecompensa:
    c = base.config(db)
    if not c.juegos_activos:
        raise HTTPException(409, "La tienda está en pausa por ahora.")
    p = db.get(m.CxPremio, premio_id)
    if not p or p.lugar != "tienda" or not p.activo or p.tipo == "puntos":
        raise HTTPException(404, "Ese premio ya no está disponible.")
    base.candado(db, u.organizacion_id)
    if base.saldo(db, u.organizacion_id) < p.costo:
        raise HTTPException(409, "Su despacho aún no tiene puntos suficientes.")
    if p.tipo == "meses" and base.meses_del_anio(db, u.organizacion_id, ("ruleta", "tienda")) + p.valor > c.tope_meses_anual:
        raise HTTPException(409, f"Su despacho ya alcanzó el máximo de {c.tope_meses_anual} meses de regalo por juegos en 12 meses.")
    base.mover(db, u.organizacion_id, u.id, "tienda", -p.costo, f"Canje: {p.etiqueta}")
    return base.otorgar(db, u.organizacion_id, "tienda", p.tipo, p.valor, f"Tienda: {p.etiqueta}")
