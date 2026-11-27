"""«Gana con Nomira» para los usuarios de los despachos: trivia, ruleta, tienda de puntos, premios,
invitaciones a otros despachos y casos de la calculadora pública (red de despachos)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, solo_admin, usuario_actual
from ..services.crecimiento import base, juegos, red

router = APIRouter(prefix="/api/premios", tags=["Gana con Nomira"])


def _premio(p: m.CxPremio) -> dict:
    return {"id": p.id, "etiqueta": p.etiqueta, "tipo": p.tipo, "valor": p.valor, "costo": p.costo}


@router.get("")
def resumen(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = base.config(db)
    org_id = u.organizacion_id
    inv = base.invitacion(db, org_id)
    giro = juegos.giro_de_semana(db, org_id)
    refs = db.scalars(select(m.CxReferido).where(m.CxReferido.referidor_id == org_id).order_by(m.CxReferido.creado_en.desc())).all()
    nombres = dict(db.execute(select(m.Organizacion.id, m.Organizacion.nombre).where(m.Organizacion.id.in_([r.referido_id for r in refs] or [0]))).all())
    recompensas = db.scalars(select(m.CxRecompensa).where(m.CxRecompensa.organizacion_id == org_id).order_by(m.CxRecompensa.id.desc())).all()
    movs = db.scalars(select(m.CxMovimiento).where(m.CxMovimiento.organizacion_id == org_id).order_by(m.CxMovimiento.id.desc()).limit(15)).all()
    cfg_red = db.scalar(select(m.CxRed).where(m.CxRed.organizacion_id == org_id))
    datos = {
        "reglas": {"juegos": c.juegos_activos, "ruleta": c.juegos_activos and c.ruleta_activa, "ruleta_permiso": c.ruleta_permiso,
                   "puntos_por_acierto": c.puntos_por_acierto, "preguntas_por_dia": c.preguntas_por_dia, "tope_puntos_dia": c.tope_puntos_dia_org,
                   "tope_meses_anual": c.tope_meses_anual, "referidos": c.referidos_activos, "meses_referido": c.meses_referido, "tope_referidos_anual": c.tope_referidos_anual,
                   "casos": c.casos_activos},
        "ya_pago": base.ya_pago(db, org_id),
        "puntos": base.saldo(db, org_id),
        "trivia": juegos.trivia_hoy(db, u) if c.juegos_activos else [],
        "ruleta": {"casillas": juegos.probabilidades(db), "girada": {"etiqueta": giro.etiqueta, "en": giro.creado_en.isoformat()} if giro else None},
        "tienda": [_premio(p) for p in juegos.tienda(db)],
        "recompensas": [base.vista_recompensa(db, r) for r in recompensas],
        "movimientos": [{"puntos": x.puntos, "detalle": x.detalle, "dia": x.dia.isoformat()} for x in movs],
        "invitacion": {"codigo": inv.codigo, "enlace": ajustes().url_publica.rstrip("/") + f"/invita/{inv.codigo}",
                       "referidos": [{"despacho": nombres.get(r.referido_id, "Despacho"), "estado": r.estado, "desde": r.creado_en.date().isoformat()} for r in refs]},
        "red": {"estados": red.ESTADOS_MX, "requisitos": red.requisitos(db, org_id),
                "config": {"activo": cfg_red.activo, "estados": cfg_red.estados, "tope_mensual": cfg_red.tope_mensual} if cfg_red else None,
                "recibidos": db.scalar(select(func.count()).select_from(m.CxCaso).where(m.CxCaso.organizacion_id == org_id))},
    }
    db.commit()
    return datos


class RespuestaIn(BaseModel):
    elegida: int = Field(ge=0, le=9)


@router.post("/trivia/{pid}")
def responder(pid: int, d: RespuestaIn, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    r = juegos.responder(db, u, pid, d.elegida)
    db.commit()
    return {**r, "puntos_total": base.saldo(db, u.organizacion_id)}


@router.post("/ruleta")
def girar(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    r = juegos.girar(db, u)
    auditar(db, u, "premios_ruleta", "cx_premio", r["premio"]["id"], {"premio": r["premio"]["etiqueta"]})
    db.commit()
    return {**r, "puntos_total": base.saldo(db, u.organizacion_id)}


@router.post("/tienda/{pid}")
def canjear(pid: int, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    r = juegos.canjear(db, u, pid)
    auditar(db, u, "premios_canje", "cx_recompensa", r.id, {"premio": r.descripcion})
    db.commit()
    return {"recompensa": base.vista_recompensa(db, r), "puntos_total": base.saldo(db, u.organizacion_id)}


class RedIn(BaseModel):
    activo: bool
    estados: list[str] = Field(default_factory=list, max_length=32)
    tope_mensual: int | None = Field(None, ge=1, le=500)


@router.put("/red")
def red_config(d: RedIn, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    estados = [e for e in dict.fromkeys(d.estados) if e in red.ESTADOS_MX]
    if d.activo and not estados:
        raise HTTPException(422, "Elija al menos un estado donde atiende casos.")
    if d.activo and not all(red.requisitos(db, u.organizacion_id).values()):
        raise HTTPException(409, "Para recibir casos necesita un plan pagado vigente y el módulo de Prospectos activo.")
    x = db.scalar(select(m.CxRed).where(m.CxRed.organizacion_id == u.organizacion_id))
    if not x:
        x = m.CxRed(organizacion_id=u.organizacion_id, estados=[])
        db.add(x)
    x.activo, x.estados, x.tope_mensual = d.activo, estados, d.tope_mensual
    auditar(db, u, "premios_red", "cx_red", None, {"activo": d.activo, "estados": estados})
    db.commit()
    return {"activo": x.activo, "estados": x.estados, "tope_mensual": x.tope_mensual}
