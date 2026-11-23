"""Vigilancia de estrados digitales dentro de Nomira Agenda Jurídica (vea services/agenda/estrados.py).

Leer: cualquier rol del despacho. Vigilar, cotejar y registrar: administrador y analista.
Todo se filtra por organización."""
from __future__ import annotations

import asyncio
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import auditar, puede_editar, usuario_actual
from ..services.agenda import base, estrados as est

router = APIRouter(prefix="/api/agenda", tags=["Nomira Agenda Jurídica · Estrados"])
MAX_PDF = 15 * 1024 * 1024


def _de_org(db: Session, modelo, oid: int | None, u: m.Usuario):
    x = db.get(modelo, oid) if oid else None
    if not x or x.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrado.")
    return x


def _mias(db: Session, u: m.Usuario):
    """Vigilancias cuyas publicaciones le tocan a esta persona (el administrador ve todas)."""
    q = select(m.AgVigilancia.id).join(m.AgAsunto, m.AgAsunto.id == m.AgVigilancia.asunto_id).where(m.AgVigilancia.organizacion_id == u.organizacion_id)
    if u.rol != "administrador":
        q = q.where((m.AgAsunto.responsable_id == u.id) | (m.AgVigilancia.creado_por_id == u.id))
    return q


def sin_ver(db: Session, u: m.Usuario) -> int:
    return db.scalar(select(func.count(m.AgPublicacion.id)).where(m.AgPublicacion.vigilancia_id.in_(_mias(db, u)),
                                                                  m.AgPublicacion.vista_en.is_(None))) or 0


def _vig_dict(db: Session, v: m.AgVigilancia, a: m.AgAsunto | None = None) -> dict:
    a = a or db.get(m.AgAsunto, v.asunto_id)
    n = db.scalar(select(func.count(m.AgPublicacion.id)).where(m.AgPublicacion.vigilancia_id == v.id)) or 0
    nv = db.scalar(select(func.count(m.AgPublicacion.id)).where(m.AgPublicacion.vigilancia_id == v.id, m.AgPublicacion.vista_en.is_(None))) or 0
    return {"id": v.id, "asunto_id": v.asunto_id, "asunto": a.titulo if a else None, "asunto_estado": a.estado if a else None,
            "fuente": v.fuente, "fuente_texto": est.FUENTES[v.fuente]["nombre"], "expediente": v.expediente, "sala": v.sala, "activa": v.activa,
            "ultima_revision": v.ultima_revision.isoformat() if v.ultima_revision else None, "ultimo_estado": v.ultimo_estado,
            "ultimo_error": v.ultimo_error, "publicaciones": n, "sin_ver": nv}


def _pub_dict(db: Session, p: m.AgPublicacion, nombres: dict | None = None) -> dict:
    v = db.get(m.AgVigilancia, p.vigilancia_id)
    a = db.get(m.AgAsunto, v.asunto_id)
    nombres = nombres if nombres is not None else {}
    return {"id": p.id, "vigilancia_id": v.id, "asunto_id": v.asunto_id, "asunto": a.titulo if a else None, "expediente": v.expediente,
            "fuente_texto": est.FUENTES[v.fuente]["nombre"], "consulta_oficial": est.FUENTES[v.fuente]["consulta"],
            "fecha_publicacion": p.fecha_publicacion.isoformat(), "surte_efectos": est.surte_efectos(db, v, p.fecha_publicacion).isoformat(),
            "sala": p.sala, "tipo": p.tipo, "descripcion": p.descripcion, "enlace": p.enlace, "origen": p.origen,
            "vista": p.vista_en is not None, "vista_por": nombres.get(p.vista_por_id), "actuacion_id": p.actuacion_id,
            "encontrada_en": p.encontrada_en.isoformat()}


def _nombres(db: Session, org: int) -> dict[int, str]:
    return dict(db.execute(select(m.Usuario.id, m.Usuario.nombre).where(m.Usuario.organizacion_id == org)).all())


# ------------------------------------------------------------------ resumen

@router.get("/estrados")
def resumen(solo_sin_ver: bool = False, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    vig = db.scalars(select(m.AgVigilancia).where(m.AgVigilancia.organizacion_id == u.organizacion_id).order_by(m.AgVigilancia.activa.desc(), m.AgVigilancia.id.desc())).all()
    q = select(m.AgPublicacion).where(m.AgPublicacion.organizacion_id == u.organizacion_id)
    if solo_sin_ver:
        q = q.where(m.AgPublicacion.vigilancia_id.in_(_mias(db, u)), m.AgPublicacion.vista_en.is_(None))
    pubs = db.scalars(q.order_by(m.AgPublicacion.fecha_publicacion.desc(), m.AgPublicacion.id.desc()).limit(100)).all()
    nombres = _nombres(db, u.organizacion_id)
    return {"automatica": est.configurado(), "fuentes": [{"clave": k, **f} for k, f in est.FUENTES.items()],
            "revisar_cada_horas": est.REVISAR_CADA_HORAS, "horario": list(est.HORARIO),
            "vigilancias": [_vig_dict(db, v) for v in vig], "publicaciones": [_pub_dict(db, p, nombres) for p in pubs],
            "sin_ver": sin_ver(db, u), "puede_editar": u.rol in ("administrador", "analista")}


# ------------------------------------------------------------------ vigilar un asunto

class VigilanciaIn(BaseModel):
    expediente: str = Field(min_length=3, max_length=80)
    sala: str | None = Field(None, max_length=120)
    fuente: str = "trijaem"
    activa: bool = True


@router.put("/asuntos/{aid}/vigilancia")
def vigilar(aid: int, d: VigilanciaIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = _de_org(db, m.AgAsunto, aid, u)
    if d.fuente not in est.FUENTES:
        raise HTTPException(422, "Tribunal no disponible.")
    if not est.clave_expediente(d.expediente):
        raise HTTPException(422, "Escriba el número de expediente como lo publica el tribunal, con número y año (por ejemplo 1234/2026).")
    v = db.scalar(select(m.AgVigilancia).where(m.AgVigilancia.asunto_id == a.id, m.AgVigilancia.fuente == d.fuente))
    if v is None:
        v = m.AgVigilancia(organizacion_id=u.organizacion_id, asunto_id=a.id, fuente=d.fuente, creado_por_id=u.id)
        db.add(v)
    cambio = v.expediente != est.normalizar_expediente(d.expediente) or (v.sala or None) != ((d.sala or "").strip() or None)
    v.expediente, v.sala, v.activa = est.normalizar_expediente(d.expediente), (d.sala or "").strip()[:120] or None, d.activa
    if cambio:
        v.ultima_revision, v.ultimo_estado, v.ultimo_error = None, "pendiente", None
    db.flush()
    auditar(db, u, "ag_estrados_vigilar", "ag_asunto", a.id, {"activa": d.activa}, request)
    db.commit()
    return _vig_dict(db, v, a)


@router.delete("/vigilancias/{vid}")
def dejar_de_vigilar(vid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    v = _de_org(db, m.AgVigilancia, vid, u)
    aid = v.asunto_id
    db.delete(v)
    auditar(db, u, "ag_estrados_quitar", "ag_asunto", aid, None, request)
    db.commit()
    return {"ok": True}


@router.post("/vigilancias/{vid}/revisar")
def revisar_ahora(vid: int, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    v = _de_org(db, m.AgVigilancia, vid, u)
    if not est.configurado(v.fuente):
        raise HTTPException(409, "La consulta automática del TRIJAEM aún no está activa en Nomira. Mientras tanto use «Cotejar lista del día».")
    nuevas = est.revisar(db, v)
    db.commit()
    est.avisar(db, nuevas, excepto=u.id)
    db.commit()
    return {"vigilancia": _vig_dict(db, v), "nuevas": len(nuevas)}


# ------------------------------------------------------------------ cotejar la lista del día

def _cotejar(db: Session, u: m.Usuario, texto: str, fecha: date, sala: str | None) -> dict:
    if fecha > base.hoy():
        raise HTTPException(422, "La fecha de publicación no puede ser futura.")
    vig = list(db.scalars(select(m.AgVigilancia).join(m.AgAsunto, m.AgAsunto.id == m.AgVigilancia.asunto_id)
                          .where(m.AgVigilancia.organizacion_id == u.organizacion_id, m.AgVigilancia.activa.is_(True), m.AgAsunto.estado == "activo")))
    if not vig:
        raise HTTPException(409, "Aún no vigila ningún expediente. Abra un asunto y active «Vigilar en estrados».")
    hallados = est.cotejar_texto(texto, fecha, vig, sala)
    nuevas, repetidas = [], 0
    por_id = {v.id: v for v in vig}
    for vid, hs in hallados.items():
        g = est.guardar(db, por_id[vid], hs, "manual")
        nuevas += g
        repetidas += len(hs) - len(g)
    db.commit()
    est.avisar(db, nuevas, excepto=u.id)
    db.commit()
    nombres = _nombres(db, u.organizacion_id)
    return {"revisados": len(vig), "encontrados": len(hallados), "nuevas": [_pub_dict(db, p, nombres) for p in nuevas], "ya_registradas": repetidas}


class CotejoIn(BaseModel):
    fecha: date
    texto: str = Field(min_length=5, max_length=2_000_000)
    sala: str | None = Field(None, max_length=120)


@router.post("/estrados/cotejar")
def cotejar(d: CotejoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    r = _cotejar(db, u, d.texto, d.fecha, (d.sala or "").strip() or None)
    auditar(db, u, "ag_estrados_cotejo", "ag_vigilancia", None, {"encontrados": r["encontrados"]}, request)
    db.commit()
    return r


@router.post("/estrados/cotejar-pdf")
async def cotejar_pdf(request: Request, archivo: UploadFile = File(...), fecha: date = Form(...), sala: str | None = Form(None),
                      u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    contenido = await archivo.read(MAX_PDF + 1)
    if len(contenido) > MAX_PDF:
        raise HTTPException(413, "El PDF pesa más de 15 MB.")
    if not contenido.startswith(b"%PDF"):
        raise HTTPException(422, "El archivo no es un PDF.")
    try:
        texto = await asyncio.to_thread(est.texto_de_pdf, contenido)
    except Exception:
        raise HTTPException(422, "No se pudo leer el PDF.")
    if len(texto.strip()) < 20:
        raise HTTPException(422, "El PDF no tiene texto seleccionable (parece una imagen escaneada). Copie y pegue la lista o use otro archivo.")
    r = _cotejar(db, u, texto, fecha, (sala or "").strip() or None)
    auditar(db, u, "ag_estrados_cotejo", "ag_vigilancia", None, {"encontrados": r["encontrados"], "pdf": True}, request)
    db.commit()
    return r


# ------------------------------------------------------------------ registrar a mano y dar seguimiento

class PublicacionIn(BaseModel):
    fecha_publicacion: date
    descripcion: str = Field(min_length=3, max_length=2000)
    tipo: str | None = Field(None, max_length=80)
    sala: str | None = Field(None, max_length=120)
    enlace: str | None = Field(None, max_length=500)


@router.post("/vigilancias/{vid}/publicaciones", status_code=201)
def registrar(vid: int, d: PublicacionIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    v = _de_org(db, m.AgVigilancia, vid, u)
    if d.fecha_publicacion > base.hoy():
        raise HTTPException(422, "La fecha de publicación no puede ser futura.")
    if d.enlace and not d.enlace.startswith("https://"):
        raise HTTPException(422, "El enlace debe empezar con https://")
    h = est.Hallazgo(fecha=d.fecha_publicacion, descripcion=d.descripcion.strip(), sala=(d.sala or "").strip() or v.sala,
                     tipo=(d.tipo or "").strip() or None, enlace=d.enlace)
    nuevas = est.guardar(db, v, [h], "manual")
    if not nuevas:
        raise HTTPException(409, "Esa publicación ya estaba registrada.")
    auditar(db, u, "ag_estrados_registro", "ag_asunto", v.asunto_id, None, request)
    db.commit()
    est.avisar(db, nuevas, excepto=u.id)
    db.commit()
    return _pub_dict(db, nuevas[0], _nombres(db, u.organizacion_id))


@router.post("/publicaciones/{pid}/vista")
def marcar_vista(pid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    p = _de_org(db, m.AgPublicacion, pid, u)
    if p.vista_en is None:
        p.vista_en, p.vista_por_id = m.ahora(), u.id
        db.commit()
    return _pub_dict(db, p, _nombres(db, u.organizacion_id))


@router.post("/publicaciones/{pid}/actuacion")
def a_actuacion(pid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """Pasa la publicación al historial del asunto como notificación por estrados, para calcular desde ahí el plazo."""
    p = _de_org(db, m.AgPublicacion, pid, u)
    if p.actuacion_id and db.get(m.AgActuacion, p.actuacion_id):
        raise HTTPException(409, "Esta publicación ya está en el historial del asunto.")
    v = db.get(m.AgVigilancia, p.vigilancia_id)
    tipo = "resolucion" if any(x in est._plano(f"{p.tipo} {p.descripcion}") for x in ("sentencia", "resolucion")) else "notificacion"
    x = m.AgActuacion(organizacion_id=u.organizacion_id, asunto_id=v.asunto_id, fecha=p.fecha_publicacion, tipo=tipo,
                      descripcion=f"Publicado en estrados ({est.FUENTES[v.fuente]['nombre']}): {p.descripcion}"[:1000],
                      notificada_en=p.fecha_publicacion, creado_por_id=u.id)
    db.add(x)
    db.flush()
    p.actuacion_id = x.id
    if p.vista_en is None:
        p.vista_en, p.vista_por_id = m.ahora(), u.id
    auditar(db, u, "ag_actuacion", "ag_asunto", v.asunto_id, {"actuacion_id": x.id, "desde": "estrados"}, request)
    db.commit()
    return {"actuacion_id": x.id, "asunto_id": v.asunto_id, "publicacion": _pub_dict(db, p, _nombres(db, u.organizacion_id))}
