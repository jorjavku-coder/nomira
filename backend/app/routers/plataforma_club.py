"""Panel de la plataforma: Club Nomira (empresas aliadas, sus beneficios, métricas y solicitudes de empresas)."""
from __future__ import annotations

import re
from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..services.agenda.base import ENTIDADES
from ..services.club import base as cb
from .organizacion import MAX_BYTES, normalizar_logo
from .plataforma import _registrar, admin_plataforma

router = APIRouter(prefix="/api/plataforma/club", tags=["Plataforma — Club Nomira"])
_RE_URL = re.compile(r"^https://[^\s]{3,490}$")


def _aliado(a: m.AlAliado, n_benef: int = 0) -> dict:
    return {"id": a.id, "nombre": a.nombre, "giro": a.giro, "sitio": a.sitio, "contacto_nombre": a.contacto_nombre,
            "contacto_email": a.contacto_email, "contacto_telefono": a.contacto_telefono, "estado": a.estado, "notas": a.notas,
            "logo": bool(a.logo_actualizado), "beneficios": n_benef, "creado_en": a.creado_en.isoformat()}


def _benef(b: m.AlBeneficio, met: dict | None = None) -> dict:
    h = cb.hoy()
    vigente = (not b.vigente_desde or b.vigente_desde <= h) and (not b.vigente_hasta or b.vigente_hasta >= h)
    return {"id": b.id, "aliado_id": b.aliado_id, "titulo": b.titulo, "resumen": b.resumen, "descripcion": b.descripcion,
            "categoria": b.categoria, "canje": b.canje, "codigo": b.codigo, "enlace": b.enlace, "condiciones": b.condiciones,
            "cobertura": b.cobertura, "vigente_desde": b.vigente_desde.isoformat() if b.vigente_desde else None,
            "vigente_hasta": b.vigente_hasta.isoformat() if b.vigente_hasta else None, "destacado": b.destacado, "estado": b.estado,
            "en_fechas": vigente, "metricas": met or {"vistas": 0, "canjes": 0, "despachos": 0}}


@router.get("")
def resumen(dias: int = 90, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    aliados = db.scalars(select(m.AlAliado).order_by(m.AlAliado.nombre)).all()
    beneficios = db.scalars(select(m.AlBeneficio).order_by(m.AlBeneficio.actualizado_en.desc())).all()
    met = cb.metricas(db, cb.hoy() - timedelta(days=max(1, min(dias, 3650))))
    por_aliado: dict[int, int] = {}
    for b in beneficios:
        por_aliado[b.aliado_id] = por_aliado.get(b.aliado_id, 0) + 1
    sols = db.scalars(select(m.AlSolicitud).order_by(m.AlSolicitud.creado_en.desc()).limit(300)).all()
    miembros = db.scalar(select(func.count(m.AlCredencial.id))) or 0
    return {"aliados": [_aliado(x, por_aliado.get(x.id, 0)) for x in aliados],
            "beneficios": [_benef(b, met.get(b.id)) for b in beneficios],
            "solicitudes": [{"id": s.id, "empresa": s.empresa, "giro": s.giro, "nombre": s.nombre, "email": s.email, "telefono": s.telefono,
                             "propuesta": s.propuesta, "estado": s.estado, "nota": s.nota, "creado_en": s.creado_en.isoformat()} for s in sols],
            "cifras": {"aliados_activos": sum(1 for x in aliados if x.estado == "activo"), "publicados": len(cb.visibles(db)),
                       "vistas": sum(v["vistas"] for v in met.values()), "canjes": sum(v["canjes"] for v in met.values()),
                       "solicitudes_nuevas": sum(1 for s in sols if s.estado == "nueva"), "credenciales": miembros},
            "categorias": cb.CATEGORIAS, "canjes": cb.CANJES, "entidades": ENTIDADES, "dias": dias}


class AliadoIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=200)
    giro: str | None = Field(None, max_length=120)
    sitio: str | None = Field(None, max_length=300)
    contacto_nombre: str | None = Field(None, max_length=200)
    contacto_email: str | None = Field(None, max_length=254)
    contacto_telefono: str | None = Field(None, max_length=30)
    estado: str = "prospecto"
    notas: str | None = Field(None, max_length=5000)
    solicitud_id: int | None = None  # si nace de una postulación del sitio


def _validar_aliado(d: AliadoIn) -> dict:
    if d.estado not in ("prospecto", "activo", "pausado"):
        raise HTTPException(422, "Estado no válido.")
    if d.sitio and not _RE_URL.match(d.sitio.strip()):
        raise HTTPException(422, "El sitio debe empezar con https://")
    datos = d.model_dump(exclude={"solicitud_id"})
    return {k: (v.strip() or None) if isinstance(v, str) and k != "estado" else v for k, v in datos.items()}


@router.post("/aliados", status_code=201)
def crear_aliado(d: AliadoIn, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    x = m.AlAliado(**_validar_aliado(d))
    db.add(x)
    db.flush()
    if d.solicitud_id:
        s = db.get(m.AlSolicitud, d.solicitud_id)
        if s:
            s.estado = "aliado"
    _registrar(db, a, "club_aliado_creado", request, entidad="al_aliado", entidad_id=x.id)
    db.commit()
    return _aliado(x)


@router.put("/aliados/{aid}")
def editar_aliado(aid: int, d: AliadoIn, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    x = db.get(m.AlAliado, aid)
    if not x:
        raise HTTPException(404, "No encontrado.")
    for k, v in _validar_aliado(d).items():
        setattr(x, k, v)
    _registrar(db, a, "club_aliado_editado", request, entidad="al_aliado", entidad_id=x.id, detalle={"estado": x.estado})
    db.commit()
    return _aliado(x)


@router.put("/aliados/{aid}/logo")
def logo_aliado(aid: int, request: Request, archivo: UploadFile = File(...), a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    x = db.get(m.AlAliado, aid)
    if not x:
        raise HTTPException(404, "No encontrado.")
    x.logo, x.logo_actualizado = normalizar_logo(archivo.file.read(MAX_BYTES + 1)), m.ahora()
    _registrar(db, a, "club_aliado_logo", request, entidad="al_aliado", entidad_id=x.id)
    db.commit()
    return _aliado(x)


@router.delete("/aliados/{aid}")
def borrar_aliado(aid: int, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    x = db.get(m.AlAliado, aid)
    if not x:
        raise HTTPException(404, "No encontrado.")
    db.delete(x)  # se van sus beneficios y sus métricas
    _registrar(db, a, "club_aliado_borrado", request, entidad="al_aliado", entidad_id=aid)
    db.commit()
    return {"ok": True}


class BeneficioIn(BaseModel):
    aliado_id: int
    titulo: str = Field(min_length=3, max_length=150)
    resumen: str = Field(min_length=2, max_length=80)
    descripcion: str | None = Field(None, max_length=5000)
    categoria: str
    canje: str
    codigo: str | None = Field(None, max_length=60)
    enlace: str | None = Field(None, max_length=500)
    condiciones: str | None = Field(None, max_length=5000)
    cobertura: list[str] | None = None
    vigente_desde: date | None = None
    vigente_hasta: date | None = None
    destacado: bool = False
    estado: str = "borrador"


def _validar_benef(db: Session, d: BeneficioIn) -> dict:
    if not db.get(m.AlAliado, d.aliado_id):
        raise HTTPException(404, "Aliado no encontrado.")
    if d.categoria not in cb.CATEGORIAS:
        raise HTTPException(422, "Categoría no válida.")
    if d.canje not in cb.CANJES:
        raise HTTPException(422, "Forma de canje no válida.")
    if d.estado not in ("borrador", "publicado", "pausado"):
        raise HTTPException(422, "Estado no válido.")
    if d.canje == "codigo" and not (d.codigo or "").strip():
        raise HTTPException(422, "Escriba el código de descuento.")
    if d.canje == "enlace" and not _RE_URL.match((d.enlace or "").strip()):
        raise HTTPException(422, "El enlace debe empezar con https://")
    if d.enlace and d.enlace.strip() and not _RE_URL.match(d.enlace.strip()):
        raise HTTPException(422, "El enlace debe empezar con https://")
    if d.vigente_desde and d.vigente_hasta and d.vigente_hasta < d.vigente_desde:
        raise HTTPException(422, "La vigencia termina antes de empezar.")
    cob = [e for e in (d.cobertura or []) if e in ENTIDADES] or None
    datos = d.model_dump()
    datos["cobertura"] = cob
    for k in ("descripcion", "codigo", "enlace", "condiciones"):
        datos[k] = (datos[k] or "").strip() or None
    datos["titulo"], datos["resumen"] = d.titulo.strip(), d.resumen.strip()
    return datos


@router.post("/beneficios", status_code=201)
def crear_benef(d: BeneficioIn, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    b = m.AlBeneficio(**_validar_benef(db, d))
    db.add(b)
    db.flush()
    _registrar(db, a, "club_beneficio_creado", request, entidad="al_beneficio", entidad_id=b.id, detalle={"estado": b.estado})
    db.commit()
    return _benef(b)


@router.put("/beneficios/{bid}")
def editar_benef(bid: int, d: BeneficioIn, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    b = db.get(m.AlBeneficio, bid)
    if not b:
        raise HTTPException(404, "No encontrado.")
    for k, v in _validar_benef(db, d).items():
        setattr(b, k, v)
    _registrar(db, a, "club_beneficio_editado", request, entidad="al_beneficio", entidad_id=b.id, detalle={"estado": b.estado})
    db.commit()
    return _benef(b)


@router.delete("/beneficios/{bid}")
def borrar_benef(bid: int, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    b = db.get(m.AlBeneficio, bid)
    if not b:
        raise HTTPException(404, "No encontrado.")
    db.delete(b)
    _registrar(db, a, "club_beneficio_borrado", request, entidad="al_beneficio", entidad_id=bid)
    db.commit()
    return {"ok": True}


class SolicitudCambio(BaseModel):
    estado: str
    nota: str | None = Field(None, max_length=2000)


@router.patch("/solicitudes/{sid}")
def atender(sid: int, d: SolicitudCambio, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    s = db.get(m.AlSolicitud, sid)
    if not s:
        raise HTTPException(404, "No encontrado.")
    if d.estado not in ("nueva", "en_contacto", "aliado", "descartada"):
        raise HTTPException(422, "Estado no válido.")
    s.estado, s.nota = d.estado, (d.nota or "").strip() or s.nota
    _registrar(db, a, "club_solicitud_atendida", request, entidad="al_solicitud", entidad_id=s.id, detalle={"estado": s.estado})
    db.commit()
    return {"ok": True}
