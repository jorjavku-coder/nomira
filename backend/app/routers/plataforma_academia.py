"""Academia desde el panel de la plataforma (solo superadministrador): configuración general, cuenta
editora del catálogo, publicación de cursos con o sin costo, entrega de cursos a un despacho y
ajustes por despacho (cursos adicionales, espacio, accesos de cortesía).

El panel NO lee los cursos internos de los despachos: solo ve los de la cuenta editora (que es de
Nomira) y, por despacho, cuántos cursos y cuánto espacio usan.
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..services.academia import base, lms, nomira
from .plataforma import _registrar, superadmin

router = APIRouter(prefix="/api/plataforma/academia", tags=["Plataforma — Academia"], dependencies=[Depends(superadmin)])


def _curso_global(c: m.AcCurso, db: Session) -> dict:
    accesos = db.scalar(select(func.count(m.AcAcceso.id)).where(m.AcAcceso.curso_id == c.id, m.AcAcceso.revocado_en.is_(None))) or 0
    return {"id": c.id, "titulo": c.titulo, "materia": c.materia, "estado": c.estado, "acceso": c.acceso,
            "precio": f"{c.precio:.2f}" if c.precio is not None else None, "version": c.version, "origen_curso_id": c.origen_curso_id,
            "lecciones": len(base.lecciones(db, c.id)), "accesos": accesos, "publicado_en": c.publicado_en.isoformat() if c.publicado_en else None,
            "semilla": bool(c.clave)}


@router.get("/config")
def ver(db: Session = Depends(get_db)):
    nomira.asegurar(db)
    conf = lms.config(db)
    db.commit()
    orgs = db.execute(select(m.Organizacion.id, m.Organizacion.nombre).order_by(m.Organizacion.nombre)).all()
    editora = []
    if conf.org_editora_id:
        globales = {c.origen_curso_id: c for c in db.scalars(select(m.AcCurso).where(m.AcCurso.organizacion_id.is_(None), m.AcCurso.origen_curso_id.is_not(None)))}
        for c in db.scalars(select(m.AcCurso).where(m.AcCurso.organizacion_id == conf.org_editora_id, m.AcCurso.estado != "archivado")
                            .order_by(m.AcCurso.titulo)):
            g = globales.get(c.id)
            editora.append({"id": c.id, "titulo": c.titulo, "materia": c.materia, "estado": c.estado, "lecciones": len(base.lecciones(db, c.id)),
                            "version": c.version, "en_catalogo": _curso_global(g, db) if g else None,
                            "desactualizado": bool(g and c.contenido_actualizado_en and g.publicado_en and c.contenido_actualizado_en > g.publicado_en)})
    catalogo = [_curso_global(c, db) for c in db.scalars(select(m.AcCurso).where(m.AcCurso.organizacion_id.is_(None)).order_by(m.AcCurso.titulo))]
    return {"config": {"cursos_incluidos": conf.cursos_incluidos, "cuota_medios_mb": conf.cuota_medios_mb, "video_max_mb": conf.video_max_mb,
                       "scorm_max_mb": conf.scorm_max_mb, "org_editora_id": conf.org_editora_id},
            "organizaciones": [{"id": i, "nombre": n} for i, n in orgs], "editora": editora, "catalogo": catalogo}


class ConfigIn(BaseModel):
    cursos_incluidos: int = Field(ge=0, le=1000)
    cuota_medios_mb: int = Field(ge=0, le=1_000_000)
    video_max_mb: int = Field(ge=1, le=5000)
    scorm_max_mb: int = Field(ge=1, le=5000)
    org_editora_id: int | None = None


@router.put("/config")
def guardar(d: ConfigIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    conf = lms.config(db)
    if d.org_editora_id is not None and not db.get(m.Organizacion, d.org_editora_id):
        raise HTTPException(422, "Organización inválida.")
    for k, v in d.model_dump().items():
        setattr(conf, k, v)
    conf.actualizado_en = m.ahora()
    _registrar(db, a, "academia_config", request, entidad="ac_config", entidad_id=conf.id, detalle=d.model_dump())
    db.commit()
    return ver(db)


class CatalogoIn(BaseModel):
    acceso: str = "incluido"  # incluido | pago
    precio: Decimal | None = Field(None, ge=0, le=1_000_000)


def _validar_precio(d: CatalogoIn) -> Decimal | None:
    if d.acceso not in ("incluido", "pago"):
        raise HTTPException(422, "Acceso inválido.")
    if d.acceso == "pago" and (d.precio is None or d.precio <= 0):
        raise HTTPException(422, "Indique el precio (antes de IVA) del curso con costo.")
    return d.precio.quantize(Decimal("0.01")) if d.acceso == "pago" else None


@router.post("/editora/{cid}/publicar")
def publicar(cid: int, d: CatalogoIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    conf = lms.config(db)
    src = db.get(m.AcCurso, cid)
    if not src or not conf.org_editora_id or src.organizacion_id != conf.org_editora_id:
        raise HTTPException(404, "El curso no es de la cuenta editora.")
    g = lms.publicar_en_catalogo(db, src, d.acceso, _validar_precio(d))
    _registrar(db, a, "academia_catalogo_publicado", request, entidad="ac_curso", entidad_id=g.id,
               detalle={"origen": src.id, "acceso": g.acceso, "precio": f"{g.precio:.2f}" if g.precio is not None else None, "version": g.version})
    db.commit()
    return ver(db)


class GlobalIn(CatalogoIn):
    estado: str = "publicado"  # publicado | archivado


@router.patch("/catalogo/{cid}")
def ajustar_global(cid: int, d: GlobalIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    g = db.get(m.AcCurso, cid)
    if not g or g.organizacion_id is not None:
        raise HTTPException(404, "No encontrado.")
    if d.estado not in ("publicado", "archivado"):
        raise HTTPException(422, "Estado inválido.")
    g.acceso, g.precio = d.acceso, _validar_precio(d)
    g.estado, g.archivado_en = d.estado, (m.ahora() if d.estado == "archivado" else None)
    _registrar(db, a, "academia_catalogo_ajustado", request, entidad="ac_curso", entidad_id=g.id,
               detalle={"acceso": g.acceso, "precio": f"{g.precio:.2f}" if g.precio is not None else None, "estado": g.estado})
    db.commit()
    return ver(db)


class EntregaIn(BaseModel):
    organizacion_id: int


@router.post("/editora/{cid}/entregar")
def entregar(cid: int, d: EntregaIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    conf = lms.config(db)
    src = db.get(m.AcCurso, cid)
    if not src or not conf.org_editora_id or src.organizacion_id != conf.org_editora_id:
        raise HTTPException(404, "El curso no es de la cuenta editora.")
    if d.organizacion_id == conf.org_editora_id or not db.get(m.Organizacion, d.organizacion_id):
        raise HTTPException(422, "Elija el despacho que recibirá el curso.")
    if not base.lecciones(db, src.id):
        raise HTTPException(422, "El curso no tiene lecciones.")
    n = lms.entregar_a_despacho(db, src, d.organizacion_id)
    _registrar(db, a, "academia_curso_entregado", request, organizacion_id=d.organizacion_id, entidad="ac_curso", entidad_id=n.id,
               detalle={"origen": src.id, "titulo": src.titulo})
    db.commit()
    return {"ok": True, "curso_id": n.id, "mensaje": "El curso quedó como borrador en la Academia del despacho para que lo revise y publique."}


@router.get("/organizaciones/{oid}")
def org(oid: int, db: Session = Depends(get_db)):
    o = db.get(m.Organizacion, oid)
    if not o:
        raise HTTPException(404, "No encontrado.")
    accesos = db.execute(select(m.AcAcceso, m.AcCurso.titulo).join(m.AcCurso, m.AcCurso.id == m.AcAcceso.curso_id)
                         .where(m.AcAcceso.organizacion_id == oid).order_by(m.AcAcceso.creado_en.desc())).all()
    return {"id": o.id, "nombre": o.nombre, "limite": lms.limite(db, oid), "espacio": lms.espacio(db, oid),
            "ac_cursos_extra": o.ac_cursos_extra, "ac_cuota_medios_mb": o.ac_cuota_medios_mb,
            "accesos": [{"curso_id": x.curso_id, "curso": t, "origen": x.origen, "creado_en": x.creado_en.isoformat(),
                         "revocado_en": x.revocado_en.isoformat() if x.revocado_en else None} for x, t in accesos]}


class OrgIn(BaseModel):
    ac_cursos_extra: int = Field(ge=0, le=10_000)
    ac_cuota_medios_mb: int | None = Field(None, ge=0, le=1_000_000)


@router.patch("/organizaciones/{oid}")
def ajustar_org(oid: int, d: OrgIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    o = db.get(m.Organizacion, oid)
    if not o:
        raise HTTPException(404, "No encontrado.")
    o.ac_cursos_extra, o.ac_cuota_medios_mb = d.ac_cursos_extra, d.ac_cuota_medios_mb
    _registrar(db, a, "academia_org_ajustada", request, organizacion_id=oid, entidad="organizacion", entidad_id=oid, detalle=d.model_dump())
    db.commit()
    return org(oid, db)


class AccesoIn(BaseModel):
    curso_id: int


@router.post("/organizaciones/{oid}/accesos")
def cortesia(oid: int, d: AccesoIn, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    c = db.get(m.AcCurso, d.curso_id)
    if not db.get(m.Organizacion, oid) or not c or not lms.es_de_pago(c):
        raise HTTPException(422, "Elija un curso de Nomira con costo.")
    lms.otorgar(db, oid, c, "cortesia", admin_id=a.id)
    _registrar(db, a, "academia_acceso_cortesia", request, organizacion_id=oid, entidad="ac_curso", entidad_id=c.id)
    db.commit()
    return org(oid, db)


@router.delete("/organizaciones/{oid}/accesos/{cid}")
def revocar(oid: int, cid: int, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    x = db.scalar(select(m.AcAcceso).where(m.AcAcceso.organizacion_id == oid, m.AcAcceso.curso_id == cid, m.AcAcceso.revocado_en.is_(None)))
    if not x:
        raise HTTPException(404, "No encontrado.")
    x.revocado_en = m.ahora()  # el avance y los diplomas ya emitidos se conservan
    _registrar(db, a, "academia_acceso_revocado", request, organizacion_id=oid, entidad="ac_curso", entidad_id=cid)
    db.commit()
    return org(oid, db)
