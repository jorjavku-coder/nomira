"""Centro Legal en el panel de la plataforma: cargar y publicar versiones APROBADAS de los
documentos, datos de contacto de privacidad, solicitudes ARCO y evidencia de aceptación.
Solo quien opera Nomira entra aquí; ningún usuario de un despacho."""
from __future__ import annotations

import csv
import hashlib
import io
import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..services import legal as lg
from .legal import version_resumen
from .plataforma import _registrar, admin_plataforma

router = APIRouter(prefix="/api/plataforma/legal", tags=["Plataforma — Centro Legal"])
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _v(db: Session, vid: int) -> m.LgVersion:
    v = db.get(m.LgVersion, vid)
    if not v:
        raise HTTPException(404, "No encontrado.")
    return v


def version_admin(db: Session, v: m.LgVersion) -> dict:
    nombres = dict(db.execute(select(m.AdminPlataforma.id, m.AdminPlataforma.nombre)).all())
    eventos = db.scalar(select(func.count(m.LgEvento.id)).where(m.LgEvento.version_id == v.id)) or 0
    return {**version_resumen(v), "documento": v.documento, "numero": v.numero, "contenido": v.contenido, "aprobado_por": v.aprobado_por,
            "creado_por": nombres.get(v.creado_por_id), "creado_en": v.creado_en.isoformat(), "publicado_por": nombres.get(v.publicado_por_id),
            "retirado_en": v.retirado_en.isoformat() if v.retirado_en else None, "eventos": eventos}


@router.get("/documentos")
def documentos(a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    res = []
    for clave, d in lg.DOCUMENTOS.items():
        vs = db.scalars(select(m.LgVersion).where(m.LgVersion.documento == clave).order_by(m.LgVersion.numero.desc())).all()
        vig = lg.vigente(db, clave)
        res.append({"clave": clave, "titulo": d["titulo"], "descripcion": d["descripcion"], "evento": d["evento"], "quien": d["quien"],
                    "vigente_id": vig.id if vig else None, "versiones": [version_admin(db, v) for v in vs]})
    return res


class VersionIn(BaseModel):
    documento: str
    version: str = Field(min_length=1, max_length=30)
    titulo: str | None = Field(None, max_length=200)
    contenido: str = Field(min_length=20, max_length=300_000)
    resumen_cambios: str | None = Field(None, max_length=1000)
    requiere_aceptacion: bool = False
    vigente_desde: str | None = None


def _fecha(v: str | None):
    from datetime import date
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        raise HTTPException(422, "Fecha inválida.")


@router.post("/versiones", status_code=201)
def crear(d: VersionIn, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    """Crea un BORRADOR con el texto aprobado tal como se recibió (no se modifica ni se resume)."""
    if d.documento not in lg.DOCUMENTOS:
        raise HTTPException(422, "Documento desconocido.")
    if db.scalar(select(m.LgVersion.id).where(m.LgVersion.documento == d.documento, m.LgVersion.version == d.version.strip())):
        raise HTTPException(409, "Ya existe una versión con esa etiqueta para este documento.")
    numero = (db.scalar(select(func.max(m.LgVersion.numero)).where(m.LgVersion.documento == d.documento)) or 0) + 1
    v = m.LgVersion(documento=d.documento, numero=numero, version=d.version.strip(), titulo=(d.titulo or "").strip() or lg.DOCUMENTOS[d.documento]["titulo"],
                    contenido=d.contenido.replace("\r\n", "\n"), resumen_cambios=(d.resumen_cambios or "").strip() or None,
                    requiere_aceptacion=d.requiere_aceptacion, vigente_desde=_fecha(d.vigente_desde), estado="borrador", creado_por_id=a.id)
    db.add(v)
    db.flush()
    _registrar(db, a, "legal_version_creada", request, entidad="lg_version", entidad_id=v.id, detalle={"documento": v.documento, "version": v.version})
    db.commit()
    return version_admin(db, v)


class VersionCambio(BaseModel):
    version: str | None = Field(None, min_length=1, max_length=30)
    titulo: str | None = Field(None, max_length=200)
    contenido: str | None = Field(None, min_length=20, max_length=300_000)
    resumen_cambios: str | None = Field(None, max_length=1000)
    requiere_aceptacion: bool | None = None
    vigente_desde: str | None = None


@router.patch("/versiones/{vid}")
def cambiar(vid: int, d: VersionCambio, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    v = _v(db, vid)
    if v.estado != "borrador":
        raise HTTPException(409, "Una versión publicada no se modifica: cree una versión nueva.")
    datos = d.model_dump(exclude_unset=True)
    if "contenido" in datos:
        v.contenido = datos["contenido"].replace("\r\n", "\n")
    for k in ("version", "titulo", "resumen_cambios"):
        if k in datos:
            setattr(v, k, (datos[k] or "").strip() or (v.version if k == "version" else None))
    if "requiere_aceptacion" in datos:
        v.requiere_aceptacion = bool(datos["requiere_aceptacion"])
    if "vigente_desde" in datos:
        v.vigente_desde = _fecha(datos["vigente_desde"])
    _registrar(db, a, "legal_version_editada", request, entidad="lg_version", entidad_id=v.id, detalle={"campos": sorted(datos)})
    db.commit()
    return version_admin(db, v)


@router.delete("/versiones/{vid}")
def borrar_borrador(vid: int, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    v = _v(db, vid)
    if v.estado != "borrador":
        raise HTTPException(409, "Solo se pueden borrar borradores. Una versión publicada queda en el historial.")
    db.delete(v)
    _registrar(db, a, "legal_borrador_eliminado", request, entidad="lg_version", entidad_id=vid)
    db.commit()
    return {"ok": True}


class Publicar(BaseModel):
    confirmo_aprobacion: bool = False
    aprobado_por: str = Field("", max_length=300)


@router.post("/versiones/{vid}/publicar")
def publicar(vid: int, d: Publicar, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    """Publica una versión ya revisada y aprobada. Queda fija: su huella SHA-256 permite probar
    después qué texto exacto estaba vigente."""
    v = _v(db, vid)
    if v.estado != "borrador":
        raise HTTPException(409, "Esta versión ya fue publicada o retirada.")
    if not d.confirmo_aprobacion or len(d.aprobado_por.strip()) < 3:
        raise HTTPException(422, "Confirme que el texto fue revisado y aprobado, e indique por quién (responsable de Nomira y abogado).")
    v.sha256 = hashlib.sha256(v.contenido.encode()).hexdigest()
    v.estado, v.aprobado_por, v.publicado_por_id, v.publicado_en = "publicada", d.aprobado_por.strip(), a.id, m.ahora()
    if v.vigente_desde is None:
        v.vigente_desde = v.publicado_en.date()
    _registrar(db, a, "legal_version_publicada", request, entidad="lg_version", entidad_id=v.id,
               detalle={"documento": v.documento, "version": v.version, "sha256": v.sha256, "requiere_aceptacion": v.requiere_aceptacion})
    db.commit()
    return version_admin(db, v)


@router.post("/versiones/{vid}/retirar")
def retirar(vid: int, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    """Deja de mostrarla como vigente (queda en el historial y en la evidencia de quien la aceptó)."""
    v = _v(db, vid)
    if v.estado != "publicada":
        raise HTTPException(409, "Solo se retira una versión publicada.")
    v.estado, v.retirado_en = "retirada", m.ahora()
    _registrar(db, a, "legal_version_retirada", request, entidad="lg_version", entidad_id=v.id, detalle={"documento": v.documento, "version": v.version})
    db.commit()
    return version_admin(db, v)


# ---------- contacto de privacidad ----------

@router.get("/config")
def ver_config(a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    c = lg.config(db)
    db.commit()
    return {"correo_privacidad": c.correo_privacidad, "responsable_datos": c.responsable_datos, "marketing_habilitado": c.marketing_habilitado}


class ConfigIn(BaseModel):
    correo_privacidad: str | None = Field(None, max_length=254)
    responsable_datos: str | None = Field(None, max_length=200)
    marketing_habilitado: bool = False


@router.put("/config")
def guardar_config(d: ConfigIn, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    c = lg.config(db)
    correo = (d.correo_privacidad or "").strip().lower() or None
    if correo and not _RE_EMAIL.match(correo):
        raise HTTPException(422, "Correo inválido.")
    c.correo_privacidad, c.responsable_datos, c.marketing_habilitado = correo, (d.responsable_datos or "").strip() or None, d.marketing_habilitado
    _registrar(db, a, "legal_config_actualizada", request, detalle={"marketing_habilitado": d.marketing_habilitado})
    db.commit()
    return ver_config(a, db)


# ---------- solicitudes ARCO ----------

def arco_dict(s: m.LgSolicitud, notas: list | None = None, nombres: dict | None = None) -> dict:
    hoy = m.ahora().date()
    abierta = s.estado not in ("atendida", "improcedente")
    return {"id": s.id, "folio": s.folio, "tipo": s.tipo, "tipo_texto": lg.TIPOS_ARCO.get(s.tipo, s.tipo), "relacion": s.relacion,
            "relacion_texto": lg.RELACIONES.get(s.relacion, s.relacion), "despacho": s.despacho, "nombre": s.nombre, "email": s.email,
            "descripcion": s.descripcion, "estado": s.estado, "estado_texto": lg.ESTADOS_ARCO.get(s.estado, s.estado),
            "recibida_en": s.recibida_en.isoformat(), "vence_en": s.vence_en.isoformat() if s.vence_en else None,
            "vencida": bool(abierta and s.vence_en and s.vence_en < hoy), "atendida_en": s.atendida_en.isoformat() if s.atendida_en else None,
            "notas": [{"estado": n.estado, "estado_texto": lg.ESTADOS_ARCO.get(n.estado, n.estado), "nota": n.nota, "admin": (nombres or {}).get(n.admin_id),
                       "creado_en": n.creado_en.isoformat()} for n in (notas or [])]}


@router.get("/arco")
def lista_arco(a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    nombres = dict(db.execute(select(m.AdminPlataforma.id, m.AdminPlataforma.nombre)).all())
    xs = db.scalars(select(m.LgSolicitud).order_by(m.LgSolicitud.recibida_en.desc())).all()
    notas: dict[int, list] = {}
    for n in db.scalars(select(m.LgSolicitudNota).order_by(m.LgSolicitudNota.creado_en)):
        notas.setdefault(n.solicitud_id, []).append(n)
    return {"solicitudes": [arco_dict(s, notas.get(s.id), nombres) for s in xs], "estados": lg.ESTADOS_ARCO}


class ArcoCambio(BaseModel):
    estado: str
    nota: str | None = Field(None, max_length=4000)


@router.post("/arco/{sid}")
def actualizar_arco(sid: int, d: ArcoCambio, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    s = db.get(m.LgSolicitud, sid)
    if not s:
        raise HTTPException(404, "No encontrado.")
    if d.estado not in lg.ESTADOS_ARCO:
        raise HTTPException(422, "Estado inválido.")
    if d.estado in ("atendida", "improcedente", "remitida_al_despacho") and not (d.nota or "").strip():
        raise HTTPException(422, "Describa qué se respondió o hizo y por qué medio (queda como evidencia).")
    s.estado = d.estado
    s.atendida_en = m.ahora() if d.estado in ("atendida", "improcedente") else None
    db.add(m.LgSolicitudNota(solicitud_id=s.id, estado=d.estado, nota=(d.nota or "").strip() or None, admin_id=a.id))
    _registrar(db, a, "legal_arco_actualizada", request, entidad="lg_solicitud", entidad_id=s.id, detalle={"estado": d.estado})
    db.commit()
    return {"ok": True}


# ---------- evidencia de aceptación ----------

@router.get("/evidencia")
def evidencia(documento: str | None = None, formato: str = "json", a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    q = select(m.LgEvento).order_by(m.LgEvento.creado_en.desc())
    if documento:
        q = q.where(m.LgEvento.documento == documento)
    evs = db.scalars(q.limit(20000)).all()
    usuarios = {u.id: u for u in db.scalars(select(m.Usuario).where(m.Usuario.id.in_({e.usuario_id for e in evs if e.usuario_id})))}
    orgs = dict(db.execute(select(m.Organizacion.id, m.Organizacion.nombre)).all())
    vs = {v.id: v for v in db.scalars(select(m.LgVersion).where(m.LgVersion.id.in_({e.version_id for e in evs if e.version_id})))}
    filas = [{"fecha": e.creado_en.isoformat(), "documento": e.documento, "version": vs[e.version_id].version if e.version_id in vs else None,
              "sha256": vs[e.version_id].sha256 if e.version_id in vs else None, "evento": e.evento, "contexto": e.contexto,
              "organizacion": orgs.get(e.organizacion_id), "usuario": usuarios[e.usuario_id].email if e.usuario_id in usuarios else None,
              "solicitud_informes": e.solicitud_id} for e in evs]
    if formato == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(filas[0].keys()) if filas else ["fecha"])
        w.writeheader()
        for f in filas:
            w.writerow({k: ("'" + str(v) if isinstance(v, str) and v[:1] in "=+-@" else v) for k, v in f.items()})
        return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="evidencia-legal.csv"', "Cache-Control": "no-store",
                                 "Access-Control-Expose-Headers": "Content-Disposition"})
    return filas[:500]
