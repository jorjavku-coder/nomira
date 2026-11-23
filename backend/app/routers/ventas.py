"""Ventas de Nomira: CRM interno del panel de la plataforma (todos los empleados de Nomira con acceso al panel).

Contactos (prospectos), oportunidades por etapa, actividades y tareas, campañas con sus resultados y la liga con
las cotizaciones del módulo Comercial. Son datos de prospectos de Nomira: no toca expedientes de los despachos.
Borrar contactos y campañas: solo superadministrador."""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, condecimal
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..services.agenda.base import ZONA
from ..services.comercial import base as cm
from ..services.ventas import base as vb
from .plataforma import _registrar, admin_plataforma, superadmin

router = APIRouter(prefix="/api/plataforma/ventas", tags=["Plataforma — Ventas (CRM)"], dependencies=[Depends(admin_plataforma)])
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
Monto = condecimal(ge=0, max_digits=12, decimal_places=2)


def _txt(v: str | None, n: int) -> str | None:
    v = re.sub(r"\s+", " ", v or "").strip()
    return v[:n] or None


def _admins(db: Session) -> dict[int, str]:
    return dict(db.execute(select(m.AdminPlataforma.id, m.AdminPlataforma.nombre)).all())


def _get(db: Session, modelo, oid: int):
    x = db.get(modelo, oid)
    if not x:
        raise HTTPException(404, "No encontrado.")
    return x


def _admin_valido(db: Session, aid: int | None) -> int | None:
    if aid is None:
        return None
    x = db.get(m.AdminPlataforma, aid)
    if not x or not x.activo:
        raise HTTPException(422, "Esa persona no es parte del equipo de Nomira.")
    return aid


def _campana_valida(db: Session, cid: int | None) -> int | None:
    if cid is not None:
        _get(db, m.VtCampana, cid)
    return cid


def _ahora_local() -> datetime:
    return datetime.now(ZONA)


# ------------------------------------------------------------------ catálogos

@router.get("/catalogos")
def catalogos(a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    paquetes = [p.nombre for p in db.scalars(select(m.CmPaquete).where(m.CmPaquete.estado == "activo").order_by(m.CmPaquete.precio_mensual))]
    return {"etapas": [{"clave": k, "nombre": n, "probabilidad": p} for k, n, p in vb.ETAPAS], "abiertas": vb.ABIERTAS,
            "canales": vb.CANALES, "origenes": vb.ORIGENES, "tipos": vb.TIPOS, "motivos": vb.MOTIVOS, "paquetes": paquetes,
            "equipo": [{"id": x.id, "nombre": x.nombre} for x in db.scalars(select(m.AdminPlataforma).where(m.AdminPlataforma.activo.is_(True)).order_by(m.AdminPlataforma.nombre))],
            "campanas": [{"id": c.id, "nombre": c.nombre, "estado": c.estado} for c in db.scalars(select(m.VtCampana).order_by(m.VtCampana.id.desc()))],
            "yo": a.id, "es_super": a.rol == "superadministrador"}


# ------------------------------------------------------------------ resumen y tablero

def _op_dict(o: m.VtOportunidad, ct: m.VtContacto | None, admins: dict, extra: dict | None = None) -> dict:
    return {"id": o.id, "titulo": o.titulo, "etapa": o.etapa, "etapa_texto": vb.NOMBRE_ETAPA[o.etapa], "probabilidad": vb.PROB[o.etapa],
            "valor_mensual": vb.dinero(o.valor_mensual), "paquete_interes": o.paquete_interes, "modulos_interes": o.modulos_interes or [],
            "cierre_estimado": o.cierre_estimado.isoformat() if o.cierre_estimado else None, "origen": o.origen, "campana_id": o.campana_id,
            "propietario_id": o.propietario_id, "propietario": admins.get(o.propietario_id), "motivo_perdida": o.motivo_perdida,
            "motivo_texto": vb.MOTIVOS.get(o.motivo_perdida or ""), "nota_cierre": o.nota_cierre, "cerrada_en": o.cerrada_en.isoformat() if o.cerrada_en else None,
            "organizacion_id": o.organizacion_id, "ultima_actividad_en": o.ultima_actividad_en.isoformat(), "creado_en": o.creado_en.isoformat(),
            "contacto": {"id": ct.id, "nombre": ct.nombre, "despacho": ct.despacho, "email": ct.email, "telefono": ct.telefono} if ct else None,
            **(extra or {})}


@router.get("/tablero")
def tablero(propietario_id: int | None = None, campana_id: int | None = None, q: str | None = None, db: Session = Depends(get_db)):
    vb.sincronizar(db)
    db.commit()
    s = select(m.VtOportunidad, m.VtContacto).join(m.VtContacto, m.VtContacto.id == m.VtOportunidad.contacto_id)
    hace30 = m.ahora() - timedelta(days=30)
    s = s.where(or_(m.VtOportunidad.etapa.in_(vb.ABIERTAS), m.VtOportunidad.cerrada_en >= hace30))
    if propietario_id:
        s = s.where(m.VtOportunidad.propietario_id == propietario_id)
    if campana_id:
        s = s.where(m.VtOportunidad.campana_id == campana_id)
    if q and q.strip():
        t = f"%{q.strip()[:80]}%"
        s = s.where(or_(m.VtOportunidad.titulo.ilike(t), m.VtContacto.nombre.ilike(t), m.VtContacto.despacho.ilike(t), m.VtContacto.email.ilike(t)))
    admins = _admins(db)
    pend = dict(db.execute(select(m.VtActividad.oportunidad_id, func.min(m.VtActividad.vence_en))
                           .where(m.VtActividad.completada_en.is_(None), m.VtActividad.vence_en.is_not(None)).group_by(m.VtActividad.oportunidad_id)).all())
    filas = [_op_dict(o, ct, admins, {"proxima_tarea": pend[o.id].isoformat() if pend.get(o.id) else None})
             for o, ct in db.execute(s.order_by(m.VtOportunidad.ultima_actividad_en.desc()).limit(1000)).all()]
    columnas = {k: [f for f in filas if f["etapa"] == k] for k, _n, _p in vb.ETAPAS}
    tot = {k: {"n": len(v), "valor": vb.dinero(sum((Decimal(f["valor_mensual"] or 0) for f in v), Decimal(0)))} for k, v in columnas.items()}
    return {"columnas": columnas, "totales": tot}


@router.get("/resumen")
def resumen(a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    vb.sincronizar(db)
    db.commit()
    hoy = _ahora_local()
    inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    abiertas = db.scalars(select(m.VtOportunidad).where(m.VtOportunidad.etapa.in_(vb.ABIERTAS))).all()
    pipeline = sum((o.valor_mensual or Decimal(0) for o in abiertas), Decimal(0))
    ponderado = sum(((o.valor_mensual or Decimal(0)) * vb.PROB[o.etapa] / 100 for o in abiertas), Decimal(0))
    ganadas_mes = db.scalars(select(m.VtOportunidad).where(m.VtOportunidad.etapa == "ganado", m.VtOportunidad.cerrada_en >= inicio_mes)).all()
    cerradas_90 = db.execute(select(m.VtOportunidad.etapa, func.count()).where(m.VtOportunidad.cerrada_en >= m.ahora() - timedelta(days=90))
                             .group_by(m.VtOportunidad.etapa)).all()
    c90 = dict(cerradas_90)
    conversion = round(100 * c90.get("ganado", 0) / (c90.get("ganado", 0) + c90.get("perdido", 0))) if (c90.get("ganado", 0) + c90.get("perdido", 0)) else None
    fin_hoy = hoy.replace(hour=23, minute=59, second=59)
    mias = select(m.VtActividad).where(m.VtActividad.completada_en.is_(None), m.VtActividad.vence_en.is_not(None),
                                       or_(m.VtActividad.asignado_id == a.id, m.VtActividad.asignado_id.is_(None)))
    vencidas = db.scalar(select(func.count()).select_from(mias.where(m.VtActividad.vence_en < hoy).subquery()))
    para_hoy = db.scalar(select(func.count()).select_from(mias.where(m.VtActividad.vence_en >= hoy, m.VtActividad.vence_en <= fin_hoy).subquery()))
    sin_contactar = sum(1 for o in abiertas if o.etapa == "nuevo")
    admins = _admins(db)
    por_vendedor = defaultdict(lambda: {"abiertas": 0, "valor": Decimal(0), "ganadas_mes": 0})
    for o in abiertas:
        x = por_vendedor[o.propietario_id]
        x["abiertas"] += 1
        x["valor"] += o.valor_mensual or Decimal(0)
    for o in ganadas_mes:
        por_vendedor[o.propietario_id]["ganadas_mes"] += 1
    motivos = dict(db.execute(select(m.VtOportunidad.motivo_perdida, func.count()).where(m.VtOportunidad.etapa == "perdido",
                                                                                         m.VtOportunidad.cerrada_en >= m.ahora() - timedelta(days=90))
                              .group_by(m.VtOportunidad.motivo_perdida)).all())
    return {"pipeline": vb.dinero(pipeline), "ponderado": vb.dinero(ponderado), "abiertas": len(abiertas), "sin_contactar": sin_contactar,
            "ganadas_mes": len(ganadas_mes), "mrr_ganado_mes": vb.dinero(sum((o.valor_mensual or Decimal(0) for o in ganadas_mes), Decimal(0))),
            "conversion_90": conversion, "tareas_vencidas": vencidas, "tareas_hoy": para_hoy,
            "por_etapa": [{"clave": k, "nombre": n, "n": sum(1 for o in abiertas if o.etapa == k)} for k, n, _p in vb.ETAPAS[:5]],
            "por_vendedor": [{"id": k, "nombre": admins.get(k, "Sin asignar"), "abiertas": v["abiertas"], "valor": vb.dinero(v["valor"]), "ganadas_mes": v["ganadas_mes"]}
                             for k, v in sorted(por_vendedor.items(), key=lambda kv: -kv[1]["valor"])],
            "motivos_perdida": [{"motivo": vb.MOTIVOS.get(k or "otro", k), "n": n} for k, n in motivos.items()]}


# ------------------------------------------------------------------ contactos

class ContactoIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=200)
    despacho: str | None = Field(None, max_length=200)
    cargo: str | None = Field(None, max_length=120)
    email: str | None = Field(None, max_length=254)
    telefono: str | None = Field(None, max_length=40)
    ciudad: str | None = Field(None, max_length=120)
    entidad: str | None = Field(None, max_length=40)
    abogados: int | None = Field(None, ge=1, le=100000)
    especialidad: str | None = Field(None, max_length=160)
    origen: str = "otro"
    campana_id: int | None = None
    propietario_id: int | None = None
    etiquetas: list[str] = Field(default_factory=list, max_length=20)
    notas: str | None = Field(None, max_length=5000)
    no_contactar: bool = False


def _aplicar_contacto(db: Session, c: m.VtContacto, d: ContactoIn) -> None:
    if d.origen not in vb.ORIGENES:
        raise HTTPException(422, "Origen no válido.")
    email = (d.email or "").strip().lower() or None
    if email and not _RE_EMAIL.match(email):
        raise HTTPException(422, "Correo electrónico inválido.")
    c.nombre, c.despacho, c.cargo, c.email = _txt(d.nombre, 200), _txt(d.despacho, 200), _txt(d.cargo, 120), email
    c.telefono, c.ciudad, c.entidad, c.abogados = _txt(d.telefono, 40), _txt(d.ciudad, 120), _txt(d.entidad, 40), d.abogados
    c.especialidad, c.origen = _txt(d.especialidad, 160), d.origen
    c.campana_id, c.propietario_id = _campana_valida(db, d.campana_id), _admin_valido(db, d.propietario_id)
    c.etiquetas = list(dict.fromkeys(t.strip()[:40] for t in d.etiquetas if t and t.strip()))[:20]
    c.notas, c.no_contactar = (d.notas or "").strip()[:5000] or None, d.no_contactar


def _ct_dict(c: m.VtContacto, admins: dict, campanas: dict | None = None) -> dict:
    return {"id": c.id, "nombre": c.nombre, "despacho": c.despacho, "cargo": c.cargo, "email": c.email, "telefono": c.telefono, "ciudad": c.ciudad,
            "entidad": c.entidad, "abogados": c.abogados, "especialidad": c.especialidad, "origen": c.origen, "origen_texto": vb.ORIGENES.get(c.origen),
            "campana_id": c.campana_id, "campana": (campanas or {}).get(c.campana_id), "propietario_id": c.propietario_id, "propietario": admins.get(c.propietario_id),
            "organizacion_id": c.organizacion_id, "etiquetas": c.etiquetas or [], "notas": c.notas, "no_contactar": c.no_contactar,
            "creado_en": c.creado_en.isoformat()}


@router.get("/contactos")
def contactos(q: str | None = None, propietario_id: int | None = None, campana_id: int | None = None, db: Session = Depends(get_db)):
    s = select(m.VtContacto)
    if q and q.strip():
        t = f"%{q.strip()[:80]}%"
        s = s.where(or_(m.VtContacto.nombre.ilike(t), m.VtContacto.despacho.ilike(t), m.VtContacto.email.ilike(t), m.VtContacto.telefono.ilike(t),
                        m.VtContacto.ciudad.ilike(t)))
    if propietario_id:
        s = s.where(m.VtContacto.propietario_id == propietario_id)
    if campana_id:
        s = s.where(m.VtContacto.campana_id == campana_id)
    admins = _admins(db)
    campanas = dict(db.execute(select(m.VtCampana.id, m.VtCampana.nombre)).all())
    abiertas = dict(db.execute(select(m.VtOportunidad.contacto_id, func.count()).where(m.VtOportunidad.etapa.in_(vb.ABIERTAS)).group_by(m.VtOportunidad.contacto_id)).all())
    ganadas = {cid for (cid,) in db.execute(select(m.VtOportunidad.contacto_id).where(m.VtOportunidad.etapa == "ganado"))}
    return [{**_ct_dict(c, admins, campanas), "oportunidades_abiertas": abiertas.get(c.id, 0), "es_cliente": c.id in ganadas or bool(c.organizacion_id)}
            for c in db.scalars(s.order_by(m.VtContacto.actualizado_en.desc()).limit(2000))]


@router.post("/contactos", status_code=201)
def crear_contacto(d: ContactoIn, request: Request, permitir_duplicado: bool = False, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    c = m.VtContacto(creado_por_id=a.id)
    _aplicar_contacto(db, c, d)
    c.propietario_id = c.propietario_id or a.id
    if c.email and not permitir_duplicado:
        dup = db.scalar(select(m.VtContacto).where(func.lower(m.VtContacto.email) == c.email).limit(1))
        if dup:
            raise HTTPException(409, f"Ya existe el contacto «{dup.nombre}» con ese correo (#{dup.id}).")
    db.add(c)
    db.flush()
    _registrar(db, a, "ventas_contacto_creado", request, entidad="vt_contacto", entidad_id=c.id)
    db.commit()
    return ver_contacto(c.id, db)


@router.get("/contactos/{cid}")
def ver_contacto(cid: int, db: Session = Depends(get_db)):
    c = _get(db, m.VtContacto, cid)
    admins = _admins(db)
    campanas = dict(db.execute(select(m.VtCampana.id, m.VtCampana.nombre)).all())
    ops = db.scalars(select(m.VtOportunidad).where(m.VtOportunidad.contacto_id == c.id).order_by(m.VtOportunidad.id.desc())).all()
    acts = db.scalars(select(m.VtActividad).where(m.VtActividad.contacto_id == c.id).order_by(m.VtActividad.creado_en.desc()).limit(200)).all()
    org = db.get(m.Organizacion, c.organizacion_id) if c.organizacion_id else None
    return {**_ct_dict(c, admins, campanas), "organizacion": {"id": org.id, "nombre": org.nombre} if org else None,
            "oportunidades": [_op_dict(o, c, admins) for o in ops], "actividades": [_act_dict(x, admins) for x in acts]}


@router.put("/contactos/{cid}")
def editar_contacto(cid: int, d: ContactoIn, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    c = _get(db, m.VtContacto, cid)
    _aplicar_contacto(db, c, d)
    _registrar(db, a, "ventas_contacto_editado", request, entidad="vt_contacto", entidad_id=c.id)
    db.commit()
    return ver_contacto(c.id, db)


@router.delete("/contactos/{cid}")
def borrar_contacto(cid: int, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    """Para ejercer el derecho de cancelación del prospecto: borra el contacto, sus oportunidades y su historial."""
    c = _get(db, m.VtContacto, cid)
    for cot in db.scalars(select(m.CmCotizacion).join(m.VtOportunidad, m.VtOportunidad.id == m.CmCotizacion.oportunidad_id).where(m.VtOportunidad.contacto_id == c.id)):
        cot.oportunidad_id = None
    db.delete(c)
    _registrar(db, a, "ventas_contacto_borrado", request, entidad="vt_contacto", entidad_id=cid)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ oportunidades

class OportunidadIn(BaseModel):
    contacto_id: int | None = None
    contacto: ContactoIn | None = None  # alta rápida del contacto junto con la oportunidad
    titulo: str = Field(min_length=2, max_length=200)
    etapa: str = "nuevo"
    valor_mensual: Monto | None = None
    paquete_interes: str | None = Field(None, max_length=80)
    modulos_interes: list[str] = Field(default_factory=list, max_length=12)
    cierre_estimado: date | None = None
    origen: str | None = None
    campana_id: int | None = None
    propietario_id: int | None = None


def _aplicar_op(db: Session, o: m.VtOportunidad, d: OportunidadIn) -> None:
    if d.origen and d.origen not in vb.ORIGENES:
        raise HTTPException(422, "Origen no válido.")
    o.titulo, o.valor_mensual, o.paquete_interes = _txt(d.titulo, 200), d.valor_mensual, _txt(d.paquete_interes, 80)
    o.modulos_interes = [x for x in d.modulos_interes if x][:12]
    o.cierre_estimado, o.campana_id = d.cierre_estimado, _campana_valida(db, d.campana_id)
    o.propietario_id = _admin_valido(db, d.propietario_id)
    if d.origen:
        o.origen = d.origen


@router.post("/oportunidades", status_code=201)
def crear_op(d: OportunidadIn, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    if d.etapa not in vb.ABIERTAS:
        raise HTTPException(422, "Una oportunidad nueva debe empezar en una etapa abierta.")
    if d.contacto_id:
        ct = _get(db, m.VtContacto, d.contacto_id)
    elif d.contacto:
        ct = m.VtContacto(creado_por_id=a.id)
        _aplicar_contacto(db, ct, d.contacto)
        ct.propietario_id = ct.propietario_id or d.propietario_id or a.id
        db.add(ct)
        db.flush()
    else:
        raise HTTPException(422, "Elija o capture el contacto.")
    o = m.VtOportunidad(contacto_id=ct.id, etapa=d.etapa, creado_por_id=a.id, origen=ct.origen, campana_id=ct.campana_id)
    _aplicar_op(db, o, d)
    o.propietario_id = o.propietario_id or ct.propietario_id or a.id
    o.campana_id = o.campana_id or ct.campana_id
    db.add(o)
    db.flush()
    vb.actividad(db, ct.id, o.id, "sistema", f"Oportunidad creada en «{vb.NOMBRE_ETAPA[o.etapa]}»", None, a.id)
    _registrar(db, a, "ventas_oportunidad_creada", request, entidad="vt_oportunidad", entidad_id=o.id)
    db.commit()
    return ver_op(o.id, db)


@router.get("/oportunidades/{oid}")
def ver_op(oid: int, db: Session = Depends(get_db)):
    o = _get(db, m.VtOportunidad, oid)
    if vb.sincronizar(db, [o]):
        db.commit()
    ct = db.get(m.VtContacto, o.contacto_id)
    admins = _admins(db)
    cots = []
    for c in db.scalars(select(m.CmCotizacion).where(m.CmCotizacion.oportunidad_id == o.id).order_by(m.CmCotizacion.id.desc())):
        v = db.scalar(select(m.CmVersion).where(m.CmVersion.cotizacion_id == c.id, m.CmVersion.numero == c.version_actual))
        cots.append({"id": c.id, "folio": c.folio, "estado": c.estado, "estado_texto": cm.ESTADOS.get(c.estado, c.estado), "total": vb.dinero(v.total) if v else None,
                     "paquete": v.calculo.get("paquete", {}).get("nombre") if v else None, "creado_en": c.creado_en.isoformat(),
                     "ruta": f"/plataforma/comercial/cotizaciones/{c.id}"})
    acts = db.scalars(select(m.VtActividad).where(m.VtActividad.oportunidad_id == o.id).order_by(m.VtActividad.creado_en.desc())).all()
    camp = db.get(m.VtCampana, o.campana_id) if o.campana_id else None
    org = db.get(m.Organizacion, o.organizacion_id) if o.organizacion_id else None
    return _op_dict(o, ct, admins, {"cotizaciones": cots, "actividades": [_act_dict(x, admins) for x in acts],
                                    "campana": camp.nombre if camp else None, "origen_texto": vb.ORIGENES.get(o.origen),
                                    "organizacion": {"id": org.id, "nombre": org.nombre} if org else None,
                                    "contacto_completo": _ct_dict(ct, admins) if ct else None})


@router.put("/oportunidades/{oid}")
def editar_op(oid: int, d: OportunidadIn, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    o = _get(db, m.VtOportunidad, oid)
    _aplicar_op(db, o, d)
    _registrar(db, a, "ventas_oportunidad_editada", request, entidad="vt_oportunidad", entidad_id=o.id)
    db.commit()
    return ver_op(o.id, db)


class EtapaIn(BaseModel):
    etapa: str
    motivo: str | None = None
    nota: str | None = Field(None, max_length=500)


@router.post("/oportunidades/{oid}/etapa")
def cambiar_etapa(oid: int, d: EtapaIn, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    o = _get(db, m.VtOportunidad, oid)
    if d.etapa not in vb.ORDEN:
        raise HTTPException(422, "Etapa no válida.")
    if d.etapa == "perdido" and d.motivo not in vb.MOTIVOS:
        raise HTTPException(422, "Indique por qué se perdió.")
    vb.mover(db, o, d.etapa, a.id, d.motivo, _txt(d.nota, 500))
    _registrar(db, a, "ventas_etapa", request, entidad="vt_oportunidad", entidad_id=o.id, detalle={"etapa": d.etapa})
    db.commit()
    return ver_op(o.id, db)


# ------------------------------------------------------------------ actividades y tareas

def _act_dict(x: m.VtActividad, admins: dict) -> dict:
    return {"id": x.id, "contacto_id": x.contacto_id, "oportunidad_id": x.oportunidad_id, "tipo": x.tipo, "tipo_texto": vb.TIPOS.get(x.tipo, x.tipo),
            "titulo": x.titulo, "detalle": x.detalle, "vence_en": x.vence_en.isoformat() if x.vence_en else None,
            "completada_en": x.completada_en.isoformat() if x.completada_en else None, "resultado": x.resultado,
            "asignado_id": x.asignado_id, "asignado": admins.get(x.asignado_id), "creado_por": admins.get(x.creado_por_id),
            "creado_en": x.creado_en.isoformat(), "es_tarea": x.vence_en is not None}


class ActividadIn(BaseModel):
    contacto_id: int | None = None
    oportunidad_id: int | None = None
    tipo: str
    titulo: str = Field(min_length=2, max_length=200)
    detalle: str | None = Field(None, max_length=5000)
    vence_en: datetime | None = None  # con fecha: queda como pendiente
    asignado_id: int | None = None


@router.post("/actividades", status_code=201)
def crear_actividad(d: ActividadIn, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    if d.tipo not in vb.TIPOS or d.tipo == "sistema":
        raise HTTPException(422, "Tipo de actividad no válido.")
    o = _get(db, m.VtOportunidad, d.oportunidad_id) if d.oportunidad_id else None
    cid = o.contacto_id if o else d.contacto_id
    if not cid:
        raise HTTPException(422, "Indique el contacto o la oportunidad.")
    ct = _get(db, m.VtContacto, cid)
    if ct.no_contactar and d.tipo in ("llamada", "correo", "whatsapp") and not d.vence_en:
        raise HTTPException(409, "Este contacto pidió no ser contactado.")
    x = vb.actividad(db, ct.id, o.id if o else None, d.tipo, d.titulo.strip(), (d.detalle or "").strip() or None, a.id,
                     vence_en=d.vence_en, asignado_id=_admin_valido(db, d.asignado_id) or (a.id if d.vence_en else None))
    if o and o.propietario_id is None:  # quien atiende primero una oportunidad sin responsable se queda con ella
        o.propietario_id = a.id
        ct.propietario_id = ct.propietario_id or a.id
    if o and o.etapa == "nuevo" and d.tipo in ("llamada", "correo", "whatsapp", "reunion", "demo") and not d.vence_en:
        vb.mover(db, o, "contactado", a.id, automatico="Primer contacto registrado.")
        for t in db.scalars(select(m.VtActividad).where(m.VtActividad.oportunidad_id == o.id, m.VtActividad.completada_en.is_(None),
                                                        m.VtActividad.titulo == "Primer contacto con el prospecto")):
            t.completada_en, t.resultado, t.asignado_id = m.ahora(), d.titulo.strip()[:500], t.asignado_id or a.id
    db.flush()
    _registrar(db, a, "ventas_actividad", request, entidad="vt_actividad", entidad_id=x.id)
    db.commit()
    return _act_dict(x, _admins(db))


class CompletarIn(BaseModel):
    resultado: str | None = Field(None, max_length=500)


@router.post("/actividades/{aid}/completar")
def completar(aid: int, d: CompletarIn, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    x = _get(db, m.VtActividad, aid)
    if x.vence_en is None:
        raise HTTPException(409, "Esa actividad no es una tarea.")
    x.completada_en, x.resultado = m.ahora(), _txt(d.resultado, 500)
    if x.oportunidad_id:
        o = db.get(m.VtOportunidad, x.oportunidad_id)
        if o:
            o.ultima_actividad_en = m.ahora()
    db.commit()
    return _act_dict(x, _admins(db))


@router.delete("/actividades/{aid}")
def borrar_actividad(aid: int, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    x = _get(db, m.VtActividad, aid)
    if x.tipo == "sistema":
        raise HTTPException(409, "El historial automático no se borra.")
    if x.creado_por_id != a.id and a.rol != "superadministrador":
        raise HTTPException(403, "Solo quien la registró (o un superadministrador) puede borrarla.")
    db.delete(x)
    db.commit()
    return {"ok": True}


@router.get("/actividades")
def tareas(asignado: str = "yo", estado: str = "pendientes", a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    s = select(m.VtActividad, m.VtContacto, m.VtOportunidad).join(m.VtContacto, m.VtContacto.id == m.VtActividad.contacto_id) \
        .outerjoin(m.VtOportunidad, m.VtOportunidad.id == m.VtActividad.oportunidad_id).where(m.VtActividad.vence_en.is_not(None))
    if estado == "pendientes":
        s = s.where(m.VtActividad.completada_en.is_(None)).order_by(m.VtActividad.vence_en)
    else:
        s = s.where(m.VtActividad.completada_en.is_not(None)).order_by(m.VtActividad.completada_en.desc())
    if asignado == "yo":
        s = s.where(or_(m.VtActividad.asignado_id == a.id, m.VtActividad.asignado_id.is_(None)))
    elif asignado.isdigit():
        s = s.where(m.VtActividad.asignado_id == int(asignado))
    admins = _admins(db)
    ahora = m.ahora()
    return [{**_act_dict(x, admins), "contacto": ct.nombre, "despacho": ct.despacho, "telefono": ct.telefono, "email": ct.email,
             "oportunidad": o.titulo if o else None, "vencida": bool(x.completada_en is None and x.vence_en < ahora)}
            for x, ct, o in db.execute(s.limit(500)).all()]


# ------------------------------------------------------------------ campañas

class CampanaIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=160)
    canal: str = "otro"
    estado: str = "activa"
    inicio: date | None = None
    fin: date | None = None
    presupuesto: Monto | None = None
    utm_campaign: str | None = Field(None, max_length=120)
    notas: str | None = Field(None, max_length=5000)


def _aplicar_campana(c: m.VtCampana, d: CampanaIn) -> None:
    if d.canal not in vb.CANALES or d.estado not in ("activa", "pausada", "terminada"):
        raise HTTPException(422, "Revise el canal y el estado.")
    if d.inicio and d.fin and d.fin < d.inicio:
        raise HTTPException(422, "La fecha de fin no puede ser antes del inicio.")
    c.nombre, c.canal, c.estado, c.inicio, c.fin = _txt(d.nombre, 160), d.canal, d.estado, d.inicio, d.fin
    c.presupuesto, c.utm_campaign, c.notas = d.presupuesto, _txt(d.utm_campaign, 120), (d.notas or "").strip() or None


@router.get("/campanas")
def campanas(db: Session = Depends(get_db)):
    r = []
    for c in db.scalars(select(m.VtCampana).order_by(m.VtCampana.id.desc())):
        ops = db.scalars(select(m.VtOportunidad).where(m.VtOportunidad.campana_id == c.id)).all()
        contactos = db.scalar(select(func.count(m.VtContacto.id)).where(m.VtContacto.campana_id == c.id)) or 0
        ganadas = [o for o in ops if o.etapa == "ganado"]
        mrr = sum((o.valor_mensual or Decimal(0) for o in ganadas), Decimal(0))
        leads = max(contactos, len(ops))
        r.append({"id": c.id, "nombre": c.nombre, "canal": c.canal, "canal_texto": vb.CANALES.get(c.canal), "estado": c.estado,
                  "inicio": c.inicio.isoformat() if c.inicio else None, "fin": c.fin.isoformat() if c.fin else None,
                  "presupuesto": vb.dinero(c.presupuesto), "utm_campaign": c.utm_campaign, "notas": c.notas,
                  "leads": leads, "oportunidades": len(ops), "abiertas": sum(1 for o in ops if o.etapa in vb.ABIERTAS), "ganadas": len(ganadas),
                  "perdidas": sum(1 for o in ops if o.etapa == "perdido"), "mrr_ganado": vb.dinero(mrr),
                  "costo_por_lead": vb.dinero(c.presupuesto / leads) if c.presupuesto and leads else None,
                  "costo_por_cliente": vb.dinero(c.presupuesto / len(ganadas)) if c.presupuesto and ganadas else None,
                  "conversion": round(100 * len(ganadas) / len(ops)) if ops else None})
    return r


@router.post("/campanas", status_code=201)
def crear_campana(d: CampanaIn, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    c = m.VtCampana(creado_por_id=a.id)
    _aplicar_campana(c, d)
    db.add(c)
    db.flush()
    _registrar(db, a, "ventas_campana_creada", request, entidad="vt_campana", entidad_id=c.id)
    db.commit()
    return {"id": c.id}


@router.put("/campanas/{cid}")
def editar_campana(cid: int, d: CampanaIn, request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    c = _get(db, m.VtCampana, cid)
    _aplicar_campana(c, d)
    _registrar(db, a, "ventas_campana_editada", request, entidad="vt_campana", entidad_id=c.id)
    db.commit()
    return {"id": c.id}


@router.delete("/campanas/{cid}")
def borrar_campana(cid: int, request: Request, a: m.AdminPlataforma = Depends(superadmin), db: Session = Depends(get_db)):
    c = _get(db, m.VtCampana, cid)
    db.delete(c)  # contactos y oportunidades conservan su historial (campana_id queda vacío)
    _registrar(db, a, "ventas_campana_borrada", request, entidad="vt_campana", entidad_id=cid)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ solicitudes del sitio

@router.post("/importar-solicitudes")
def importar(request: Request, a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    n = vb.importar_solicitudes(db)
    _registrar(db, a, "ventas_importar_solicitudes", request, detalle={"nuevas": n})
    db.commit()
    return {"nuevas": n}


@router.get("/contador")
def contador(a: m.AdminPlataforma = Depends(admin_plataforma), db: Session = Depends(get_db)):
    vencidas = db.scalar(select(func.count(m.VtActividad.id)).where(m.VtActividad.completada_en.is_(None), m.VtActividad.vence_en < m.ahora(),
                                                                     or_(m.VtActividad.asignado_id == a.id, m.VtActividad.asignado_id.is_(None))))
    nuevas = db.scalar(select(func.count(m.VtOportunidad.id)).where(m.VtOportunidad.etapa == "nuevo"))
    return {"total": (vencidas or 0) + (nuevas or 0), "tareas_vencidas": vencidas or 0, "nuevas": nuevas or 0}
