"""API de Nomira Agenda Jurídica. Todas las rutas exigen el módulo activo (vea main.py) y se filtran
por organización. Leer: cualquier rol. Editar: administrador y analista. Configuración: administrador.

Principio: Nomira AYUDA a calcular y recordar; no decide plazos. Todo plazo calculado guarda su desglose
y queda «sin validar» hasta que un abogado lo confirma; si cambia la fecha o el cálculo, se pierde la
validación. Nomira no precarga plazos legales: los «plazos frecuentes» los define el propio despacho."""
from __future__ import annotations

import csv
import hashlib
import io
import re
import secrets
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, puede_editar, solo_admin, usuario_actual
from ..services import modulos
from ..services.agenda import base, dias as calc
from ..services.academia.sesiones import plataforma

router = APIRouter(prefix="/api/agenda", tags=["Nomira Agenda Jurídica"])
HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


# ------------------------------------------------------------------ utilidades

def _txt(v: str | None, n: int) -> str | None:
    v = (v or "").strip()
    return v[:n] or None


def _de_org(db: Session, modelo, oid: int | None, u: m.Usuario):
    x = db.get(modelo, oid) if oid else None
    if not x or x.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrado.")
    return x


def _usuario(db: Session, uid: int | None, u: m.Usuario) -> int | None:
    if not uid:
        return None
    x = db.get(m.Usuario, uid)
    if not x or x.organizacion_id != u.organizacion_id or x.eliminado_en or not x.activo:
        raise HTTPException(422, "El responsable debe ser un usuario activo de su organización.")
    return x.id


def _nombres(db: Session, org: int) -> dict[int, str]:
    return dict(db.execute(select(m.Usuario.id, m.Usuario.nombre).where(m.Usuario.organizacion_id == org)).all())


def _aud(db, u, accion, entidad, eid, request, **detalle):
    auditar(db, u, accion, entidad, eid, detalle or None, request)


def _cal_dict(db: Session, c: m.AgCalendario) -> dict:
    n = len(db.scalars(select(m.AgDia.id).where(m.AgDia.calendario_id == c.id)).all())
    return {"id": c.id, "nombre": c.nombre, "jurisdiccion": c.jurisdiccion, "entidad": c.entidad, "descripcion": c.descripcion, "fuente": c.fuente,
            "dias_semana_inhabiles": c.dias_semana_inhabiles if c.dias_semana_inhabiles is not None else [5, 6],
            "incluir_descanso_lft": c.incluir_descanso_lft, "activo": c.activo, "dias_capturados": n,
            "actualizado_en": (c.actualizado_en or c.creado_en).isoformat()}


def _asunto_dict(db: Session, a: m.AgAsunto, nombres: dict | None = None, resumen: bool = True) -> dict:
    nombres = nombres if nombres is not None else _nombres(db, a.organizacion_id)
    cal = db.get(m.AgCalendario, a.calendario_id) if a.calendario_id else None
    d = {"id": a.id, "titulo": a.titulo, "numero": a.numero, "jurisdiccion": a.jurisdiccion, "entidad": a.entidad, "tribunal": a.tribunal,
         "materia": a.materia, "materia_texto": base.MATERIAS.get(a.materia, a.materia), "calendario_id": a.calendario_id,
         "calendario": cal.nombre if cal else None, "responsable_id": a.responsable_id, "responsable": nombres.get(a.responsable_id),
         "expediente_id": a.expediente_id, "ev_asunto_id": a.ev_asunto_id, "notas": a.notas, "estado": a.estado,
         "creado_en": a.creado_en.isoformat()}
    if resumen:
        pend = db.scalars(select(m.AgEvento).where(m.AgEvento.asunto_id == a.id, m.AgEvento.estado == "pendiente").order_by(m.AgEvento.fecha)).all()
        ref = base.hoy()
        d["pendientes"] = len(pend)
        d["vencidos"] = sum(1 for e in pend if e.fecha < ref)
        d["proximo"] = _evento_dict(db, pend[0], nombres, ref) if pend else None
    return d


def _evento_dict(db: Session, e: m.AgEvento, nombres: dict | None = None, ref: date | None = None) -> dict:
    nombres = nombres if nombres is not None else _nombres(db, e.organizacion_id)
    a = db.get(m.AgAsunto, e.asunto_id) if e.asunto_id else None
    ref = ref or base.hoy()
    return {"id": e.id, "tipo": e.tipo, "tipo_texto": base.TIPOS_EVENTO[e.tipo], "titulo": e.titulo, "descripcion": e.descripcion,
            "fecha": e.fecha.isoformat(), "hora": e.hora, "duracion_min": e.duracion_min, "lugar": e.lugar, "enlace": e.enlace,
            "plataforma": plataforma(e.enlace) if e.enlace else None, "prioridad": e.prioridad,
            "responsable_id": e.responsable_id, "responsable": nombres.get(e.responsable_id),
            "apoyo_ids": e.apoyo_ids or [], "apoyo": [nombres.get(int(x)) for x in (e.apoyo_ids or []) if nombres.get(int(x))],
            "alertas": base.alertas_de(db, e), "alertas_propias": e.alertas is not None,
            "calculo": e.calculo, "validado": e.validado_en is not None, "validado_por": nombres.get(e.validado_por_id),
            "validado_en": e.validado_en.isoformat() if e.validado_en else None, "por_validar": base.pendientes_de_validar(e),
            "estado": e.estado, "situacion": base.situacion(e, ref), "faltan": (e.fecha - ref).days,
            "cumplido_en": e.cumplido_en.isoformat() if e.cumplido_en else None, "cumplido_por": nombres.get(e.cumplido_por_id),
            "nota_cierre": e.nota_cierre, "actuacion_id": e.actuacion_id,
            "asunto": {"id": a.id, "titulo": a.titulo, "numero": a.numero, "tribunal": a.tribunal, "materia": base.MATERIAS.get(a.materia, a.materia)} if a else None,
            "creado_en": e.creado_en.isoformat()}


# ------------------------------------------------------------------ catálogos y configuración

@router.get("/catalogos")
def catalogos(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    usuarios = db.scalars(select(m.Usuario).where(m.Usuario.organizacion_id == u.organizacion_id, m.Usuario.activo.is_(True),
                                                  m.Usuario.eliminado_en.is_(None)).order_by(m.Usuario.nombre))
    act = modulos.activos(db, u.organizacion_id)
    vinculos = {}
    if "nomina" in act:
        vinculos["expedientes"] = [{"id": x.id, "nombre": x.trabajador_nombre} for x in db.scalars(
            select(m.Expediente).where(m.Expediente.organizacion_id == u.organizacion_id).order_by(m.Expediente.id.desc()).limit(300))]
    if "evidencia" in act:
        vinculos["ev_asuntos"] = [{"id": x.id, "nombre": x.nombre} for x in db.scalars(
            select(m.EvAsunto).where(m.EvAsunto.organizacion_id == u.organizacion_id).order_by(m.EvAsunto.id.desc()).limit(300))]
    conf = base.config(db, u.organizacion_id)
    db.commit()
    return {"materias": base.MATERIAS, "jurisdicciones": base.JURISDICCIONES, "entidades": base.ENTIDADES, "tipos_actuacion": base.TIPOS_ACTUACION,
            "tipos_evento": base.TIPOS_EVENTO, "prioridades": base.PRIORIDADES, "surte_efectos": calc.SURTE_EFECTOS, "tipos_dias": calc.TIPOS_DIAS,
            "usuarios": [{"id": x.id, "nombre": x.nombre, "rol": x.rol} for x in usuarios],
            "calendarios": [{"id": c.id, "nombre": c.nombre} for c in db.scalars(select(m.AgCalendario).where(
                m.AgCalendario.organizacion_id == u.organizacion_id, m.AgCalendario.activo.is_(True)).order_by(m.AgCalendario.nombre))],
            "plantillas": [_plantilla_dict(p) for p in db.scalars(select(m.AgPlantilla).where(
                m.AgPlantilla.organizacion_id == u.organizacion_id, m.AgPlantilla.activo.is_(True)).order_by(m.AgPlantilla.nombre))],
            "calendario_defecto": conf.calendario_id, "alertas_plazo": base.limpiar_alertas(conf.alertas_plazo),
            "alertas_audiencia": base.limpiar_alertas(conf.alertas_audiencia), "vinculos": vinculos,
            "puede_editar": u.rol in ("administrador", "analista"), "es_admin": u.rol == "administrador", "yo": u.id}


class ConfigIn(BaseModel):
    alertas_plazo: list[int] = Field(default_factory=list, max_length=6)
    alertas_audiencia: list[int] = Field(default_factory=list, max_length=6)
    escalar_a_id: int | None = None
    resumen_diario: bool = True
    hora_resumen: int = Field(7, ge=5, le=11)
    calendario_id: int | None = None


@router.get("/config")
def ver_config(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = base.config(db, u.organizacion_id)
    db.commit()
    return {"alertas_plazo": base.limpiar_alertas(c.alertas_plazo), "alertas_audiencia": base.limpiar_alertas(c.alertas_audiencia),
            "escalar_a_id": c.escalar_a_id, "resumen_diario": c.resumen_diario, "hora_resumen": c.hora_resumen, "calendario_id": c.calendario_id}


@router.put("/config")
def guardar_config(d: ConfigIn, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    c = base.config(db, u.organizacion_id)
    if d.calendario_id:
        _de_org(db, m.AgCalendario, d.calendario_id, u)
    c.alertas_plazo, c.alertas_audiencia = base.limpiar_alertas(d.alertas_plazo), base.limpiar_alertas(d.alertas_audiencia)
    c.escalar_a_id, c.resumen_diario, c.hora_resumen, c.calendario_id = _usuario(db, d.escalar_a_id, u), d.resumen_diario, d.hora_resumen, d.calendario_id
    c.actualizado_en = m.ahora()
    _aud(db, u, "ag_config", "ag_config", c.id, request)
    db.commit()
    return ver_config(u, db)


# ------------------------------------------------------------------ calendarios judiciales

class CalendarioIn(BaseModel):
    nombre: str = Field(min_length=3, max_length=200)
    jurisdiccion: str = "federal"
    entidad: str | None = None
    descripcion: str | None = Field(None, max_length=500)
    fuente: str | None = Field(None, max_length=500)
    dias_semana_inhabiles: list[int] = Field(default_factory=lambda: [5, 6], max_length=7)
    incluir_descanso_lft: bool = True
    activo: bool = True


def _validar_cal(d: CalendarioIn) -> dict:
    if d.jurisdiccion not in base.JURISDICCIONES:
        raise HTTPException(422, "Jurisdicción inválida.")
    if d.jurisdiccion == "estatal" and d.entidad not in base.ENTIDADES:
        raise HTTPException(422, "Elija la entidad federativa.")
    if any(x not in range(7) for x in d.dias_semana_inhabiles) or len(set(d.dias_semana_inhabiles)) >= 7:
        raise HTTPException(422, "Días de la semana inválidos.")
    x = d.model_dump()
    x["entidad"] = d.entidad if d.jurisdiccion == "estatal" else None
    x["dias_semana_inhabiles"] = sorted(set(d.dias_semana_inhabiles))
    x["descripcion"], x["fuente"] = _txt(d.descripcion, 500), _txt(d.fuente, 500)
    return x


@router.get("/calendarios")
def calendarios(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return [_cal_dict(db, c) for c in db.scalars(select(m.AgCalendario).where(m.AgCalendario.organizacion_id == u.organizacion_id)
                                                 .order_by(m.AgCalendario.activo.desc(), m.AgCalendario.nombre))]


@router.post("/calendarios", status_code=201)
def crear_calendario(d: CalendarioIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = m.AgCalendario(organizacion_id=u.organizacion_id, **_validar_cal(d))
    db.add(c)
    db.flush()
    _aud(db, u, "ag_calendario_creado", "ag_calendario", c.id, request)
    db.commit()
    return _cal_dict(db, c)


@router.patch("/calendarios/{cid}")
def editar_calendario(cid: int, d: CalendarioIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _de_org(db, m.AgCalendario, cid, u)
    for k, v in _validar_cal(d).items():
        setattr(c, k, v)
    c.actualizado_en = m.ahora()
    _aud(db, u, "ag_calendario_editado", "ag_calendario", c.id, request)
    db.commit()
    return _cal_dict(db, c)


@router.get("/calendarios/{cid}/anio/{anio}")
def dias_del_anio(cid: int, anio: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Todos los días inhábiles del año (capturados + art. 74 LFT) para revisar el calendario."""
    if not 2000 <= anio <= 2100:
        raise HTTPException(422, "Año inválido.")
    c = _de_org(db, m.AgCalendario, cid, u)
    capturados = {d.fecha: d for d in db.scalars(select(m.AgDia).where(m.AgDia.calendario_id == c.id, m.AgDia.fecha >= date(anio, 1, 1),
                                                                       m.AgDia.fecha <= date(anio, 12, 31)))}
    res = [{"id": x.id, "fecha": f.isoformat(), "tipo": x.tipo, "motivo": x.motivo, "origen": "capturado"} for f, x in sorted(capturados.items())]
    if c.incluir_descanso_lft:
        for f, mot in sorted(calc.descanso_lft(anio).items()):
            if f not in capturados:
                res.append({"id": None, "fecha": f.isoformat(), "tipo": "inhabil", "motivo": mot, "origen": "lft"})
    res.sort(key=lambda x: x["fecha"])
    return {"calendario": _cal_dict(db, c), "anio": anio, "dias": res}


class DiasIn(BaseModel):
    desde: date
    hasta: date | None = None  # para periodos (vacaciones)
    motivo: str = Field(min_length=3, max_length=200)
    tipo: str = "inhabil"


@router.post("/calendarios/{cid}/dias", status_code=201)
def agregar_dias(cid: int, d: DiasIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _de_org(db, m.AgCalendario, cid, u)
    if d.tipo not in ("inhabil", "habil"):
        raise HTTPException(422, "Tipo inválido.")
    hasta = d.hasta or d.desde
    if hasta < d.desde or (hasta - d.desde).days > 62:
        raise HTTPException(422, "El periodo debe ser de máximo 62 días y la fecha final no puede ser anterior a la inicial.")
    existentes = {x.fecha: x for x in db.scalars(select(m.AgDia).where(m.AgDia.calendario_id == c.id, m.AgDia.fecha >= d.desde, m.AgDia.fecha <= hasta))}
    f, n = d.desde, 0
    while f <= hasta:
        x = existentes.get(f)
        if x:
            x.tipo, x.motivo = d.tipo, d.motivo.strip()
        else:
            db.add(m.AgDia(calendario_id=c.id, fecha=f, tipo=d.tipo, motivo=d.motivo.strip(), creado_por_id=u.id))
        n += 1
        f += timedelta(days=1)
    c.actualizado_en = m.ahora()
    _aud(db, u, "ag_calendario_dias", "ag_calendario", c.id, request, desde=d.desde.isoformat(), hasta=hasta.isoformat(), tipo=d.tipo)
    db.commit()
    return {"agregados": n, **dias_del_anio(c.id, d.desde.year, u, db)}


@router.delete("/calendarios/{cid}/dias/{did}")
def quitar_dia(cid: int, did: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = _de_org(db, m.AgCalendario, cid, u)
    x = db.get(m.AgDia, did)
    if not x or x.calendario_id != c.id:
        raise HTTPException(404, "No encontrado.")
    anio = x.fecha.year
    db.delete(x)
    c.actualizado_en = m.ahora()
    _aud(db, u, "ag_calendario_dia_quitado", "ag_calendario", c.id, request)
    db.commit()
    return dias_del_anio(c.id, anio, u, db)


# ------------------------------------------------------------------ plazos frecuentes del despacho

class PlantillaIn(BaseModel):
    nombre: str = Field(min_length=3, max_length=200)
    materia: str | None = None
    dias: int = Field(ge=1, le=calc.MAX_DIAS)
    tipo_dias: str = "habiles"
    surte_efectos: str
    fundamento: str | None = Field(None, max_length=500)
    alertas: list[int] | None = None
    activo: bool = True


def _plantilla_dict(p: m.AgPlantilla) -> dict:
    return {"id": p.id, "nombre": p.nombre, "materia": p.materia, "dias": p.dias, "tipo_dias": p.tipo_dias, "surte_efectos": p.surte_efectos,
            "fundamento": p.fundamento, "alertas": p.alertas, "activo": p.activo}


def _val_plantilla(d: PlantillaIn) -> dict:
    if d.tipo_dias not in calc.TIPOS_DIAS or d.surte_efectos not in calc.SURTE_EFECTOS:
        raise HTTPException(422, "Revise el tipo de días y cuándo surte efectos.")
    if d.materia and d.materia not in base.MATERIAS:
        raise HTTPException(422, "Materia inválida.")
    x = d.model_dump()
    x["fundamento"] = _txt(d.fundamento, 500)
    x["alertas"] = base.limpiar_alertas(d.alertas) if d.alertas is not None else None
    return x


@router.get("/plantillas")
def plantillas(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return [_plantilla_dict(p) for p in db.scalars(select(m.AgPlantilla).where(m.AgPlantilla.organizacion_id == u.organizacion_id)
                                                   .order_by(m.AgPlantilla.activo.desc(), m.AgPlantilla.nombre))]


@router.post("/plantillas", status_code=201)
def crear_plantilla(d: PlantillaIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    p = m.AgPlantilla(organizacion_id=u.organizacion_id, **_val_plantilla(d))
    db.add(p)
    db.flush()
    _aud(db, u, "ag_plantilla_creada", "ag_plantilla", p.id, request)
    db.commit()
    return _plantilla_dict(p)


@router.patch("/plantillas/{pid}")
def editar_plantilla(pid: int, d: PlantillaIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    p = _de_org(db, m.AgPlantilla, pid, u)
    for k, v in _val_plantilla(d).items():
        setattr(p, k, v)
    _aud(db, u, "ag_plantilla_editada", "ag_plantilla", p.id, request)
    db.commit()
    return _plantilla_dict(p)


# ------------------------------------------------------------------ cálculo asistido

class CalculoIn(BaseModel):
    notificacion: date
    dias: int = Field(ge=1, le=calc.MAX_DIAS)
    tipo_dias: str
    surte_efectos: str
    recorrer_inhabil: bool = True
    calendario_id: int | None = None
    asunto_id: int | None = None


def _calcular(db: Session, d: CalculoIn, u: m.Usuario) -> dict:
    cal_id = d.calendario_id
    if not cal_id and d.asunto_id:
        cal_id = _de_org(db, m.AgAsunto, d.asunto_id, u).calendario_id
    if not cal_id:
        cal_id = base.config(db, u.organizacion_id).calendario_id
    elif cal_id:
        _de_org(db, m.AgCalendario, cal_id, u)
    try:
        r = calc.calcular(base.calendario(db, cal_id, u.organizacion_id), d.notificacion, d.dias, d.tipo_dias, d.surte_efectos, d.recorrer_inhabil)
    except ValueError as e:
        raise HTTPException(422, str(e))
    r["calendario_id"] = cal_id
    if not cal_id:
        r["advertencia"] = "No eligió el calendario del tribunal: solo se saltaron fines de semana y los días del art. 74 LFT."
    return r


@router.post("/calcular")
def calcular(d: CalculoIn, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return _calcular(db, d, u)


# ------------------------------------------------------------------ asuntos

class AsuntoIn(BaseModel):
    titulo: str = Field(min_length=3, max_length=200)
    numero: str | None = Field(None, max_length=80)
    jurisdiccion: str = "federal"
    entidad: str | None = None
    tribunal: str | None = Field(None, max_length=200)
    materia: str
    calendario_id: int | None = None
    responsable_id: int | None = None
    expediente_id: int | None = None
    ev_asunto_id: int | None = None
    notas: str | None = Field(None, max_length=5000)


def _val_asunto(db: Session, d: AsuntoIn, u: m.Usuario) -> dict:
    if d.materia not in base.MATERIAS or d.jurisdiccion not in base.JURISDICCIONES:
        raise HTTPException(422, "Revise la materia y la jurisdicción.")
    if d.jurisdiccion == "estatal" and d.entidad not in base.ENTIDADES:
        raise HTTPException(422, "Elija la entidad federativa.")
    if d.calendario_id:
        _de_org(db, m.AgCalendario, d.calendario_id, u)
    if d.expediente_id:
        _de_org(db, m.Expediente, d.expediente_id, u)
    if d.ev_asunto_id:
        _de_org(db, m.EvAsunto, d.ev_asunto_id, u)
    return {"titulo": d.titulo.strip(), "numero": _txt(d.numero, 80), "jurisdiccion": d.jurisdiccion,
            "entidad": d.entidad if d.jurisdiccion == "estatal" else None, "tribunal": _txt(d.tribunal, 200), "materia": d.materia,
            "calendario_id": d.calendario_id, "responsable_id": _usuario(db, d.responsable_id, u), "expediente_id": d.expediente_id,
            "ev_asunto_id": d.ev_asunto_id, "notas": _txt(d.notas, 5000)}


@router.get("/asuntos")
def asuntos(estado: str = "activo", q: str | None = None, responsable_id: int | None = None,
            u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    s = select(m.AgAsunto).where(m.AgAsunto.organizacion_id == u.organizacion_id)
    if estado != "todos":
        s = s.where(m.AgAsunto.estado == estado)
    if responsable_id:
        s = s.where(m.AgAsunto.responsable_id == responsable_id)
    if q and q.strip():
        t = f"%{q.strip()[:80]}%"
        s = s.where(or_(m.AgAsunto.titulo.ilike(t), m.AgAsunto.numero.ilike(t), m.AgAsunto.tribunal.ilike(t)))
    nombres = _nombres(db, u.organizacion_id)
    return [_asunto_dict(db, a, nombres) for a in db.scalars(s.order_by(m.AgAsunto.actualizado_en.desc().nullslast(), m.AgAsunto.id.desc()).limit(500))]


@router.post("/asuntos", status_code=201)
def crear_asunto(d: AsuntoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = m.AgAsunto(organizacion_id=u.organizacion_id, creado_por_id=u.id, actualizado_en=m.ahora(), **_val_asunto(db, d, u))
    if not a.calendario_id:
        a.calendario_id = base.config(db, u.organizacion_id).calendario_id
    db.add(a)
    db.flush()
    _aud(db, u, "ag_asunto_creado", "ag_asunto", a.id, request)
    db.commit()
    return ver_asunto(a.id, u, db)


@router.get("/asuntos/{aid}")
def ver_asunto(aid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    a = _de_org(db, m.AgAsunto, aid, u)
    nombres = _nombres(db, u.organizacion_id)
    d = _asunto_dict(db, a, nombres, resumen=False)
    d["actuaciones"] = [{"id": x.id, "fecha": x.fecha.isoformat(), "tipo": x.tipo, "tipo_texto": base.TIPOS_ACTUACION.get(x.tipo, x.tipo),
                         "descripcion": x.descripcion, "notificada_en": x.notificada_en.isoformat() if x.notificada_en else None,
                         "por": nombres.get(x.creado_por_id)}
                        for x in db.scalars(select(m.AgActuacion).where(m.AgActuacion.asunto_id == a.id).order_by(m.AgActuacion.fecha.desc(), m.AgActuacion.id.desc()))]
    ref = base.hoy()
    d["eventos"] = [_evento_dict(db, e, nombres, ref) for e in db.scalars(select(m.AgEvento).where(m.AgEvento.asunto_id == a.id)
                                                                          .order_by(m.AgEvento.estado != "pendiente", m.AgEvento.fecha))]
    return d


@router.patch("/asuntos/{aid}")
def editar_asunto(aid: int, d: AsuntoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = _de_org(db, m.AgAsunto, aid, u)
    for k, v in _val_asunto(db, d, u).items():
        setattr(a, k, v)
    a.actualizado_en = m.ahora()
    _aud(db, u, "ag_asunto_editado", "ag_asunto", a.id, request)
    db.commit()
    return ver_asunto(a.id, u, db)


class EstadoIn(BaseModel):
    estado: str


@router.post("/asuntos/{aid}/estado")
def estado_asunto(aid: int, d: EstadoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = _de_org(db, m.AgAsunto, aid, u)
    if d.estado not in ("activo", "concluido", "archivado"):
        raise HTTPException(422, "Estado inválido.")
    if d.estado != "activo":
        pend = db.scalars(select(m.AgEvento.id).where(m.AgEvento.asunto_id == a.id, m.AgEvento.estado == "pendiente")).all()
        if pend:
            raise HTTPException(409, f"El asunto tiene {len(pend)} pendiente(s). Márquelos como cumplidos o cancélelos antes de concluirlo.")
    a.estado, a.actualizado_en = d.estado, m.ahora()
    _aud(db, u, "ag_asunto_estado", "ag_asunto", a.id, request, estado=d.estado)
    db.commit()
    return ver_asunto(a.id, u, db)


class ActuacionIn(BaseModel):
    fecha: date
    tipo: str
    descripcion: str = Field(min_length=3, max_length=1000)
    notificada_en: date | None = None


@router.post("/asuntos/{aid}/actuaciones", status_code=201)
def agregar_actuacion(aid: int, d: ActuacionIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = _de_org(db, m.AgAsunto, aid, u)
    if d.tipo not in base.TIPOS_ACTUACION:
        raise HTTPException(422, "Tipo de actuación inválido.")
    x = m.AgActuacion(organizacion_id=u.organizacion_id, asunto_id=a.id, fecha=d.fecha, tipo=d.tipo, descripcion=d.descripcion.strip(),
                      notificada_en=d.notificada_en, creado_por_id=u.id)
    db.add(x)
    a.actualizado_en = m.ahora()
    db.flush()
    _aud(db, u, "ag_actuacion", "ag_asunto", a.id, request, actuacion_id=x.id)
    db.commit()
    r = ver_asunto(a.id, u, db)
    r["actuacion_id"] = x.id
    return r


@router.delete("/actuaciones/{xid}")
def quitar_actuacion(xid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    x = _de_org(db, m.AgActuacion, xid, u)
    aid = x.asunto_id
    db.delete(x)
    _aud(db, u, "ag_actuacion_quitada", "ag_asunto", aid, request)
    db.commit()
    return ver_asunto(aid, u, db)


# ------------------------------------------------------------------ plazos, audiencias y actividades

class EventoIn(BaseModel):
    tipo: str
    titulo: str = Field(min_length=3, max_length=200)
    descripcion: str | None = Field(None, max_length=5000)
    asunto_id: int | None = None
    actuacion_id: int | None = None
    fecha: date | None = None  # obligatoria salvo que venga un cálculo
    hora: str | None = None
    duracion_min: int | None = Field(None, ge=5, le=1440)
    lugar: str | None = Field(None, max_length=300)
    enlace: str | None = Field(None, max_length=500)
    prioridad: str = "normal"
    responsable_id: int | None = None
    apoyo_ids: list[int] = Field(default_factory=list, max_length=10)
    alertas: list[int] | None = None
    calculo: CalculoIn | None = None


def _aplicar(db: Session, e: m.AgEvento, d: EventoIn, u: m.Usuario) -> None:
    if d.tipo not in base.TIPOS_EVENTO or d.prioridad not in base.PRIORIDADES:
        raise HTTPException(422, "Revise el tipo y la prioridad.")
    if d.hora and not HORA.match(d.hora):
        raise HTTPException(422, "Hora inválida (use HH:MM).")
    if d.enlace and not d.enlace.startswith("https://"):
        raise HTTPException(422, "El enlace debe empezar con https://")
    if d.asunto_id:
        a = _de_org(db, m.AgAsunto, d.asunto_id, u)
        if a.estado != "activo" and e.asunto_id != a.id:
            raise HTTPException(409, "El asunto no está activo.")
    if d.actuacion_id:
        x = _de_org(db, m.AgActuacion, d.actuacion_id, u)
        if x.asunto_id != d.asunto_id:
            raise HTTPException(422, "La actuación no pertenece a ese asunto.")
    antes = (e.fecha, e.calculo)
    if d.calculo:
        if d.tipo != "plazo":
            raise HTTPException(422, "El cálculo de días solo aplica a plazos.")
        if not d.calculo.asunto_id:
            d.calculo.asunto_id = d.asunto_id
        r = _calcular(db, d.calculo, u)
        r["ajuste_manual"] = None
        fecha = date.fromisoformat(r["vence"])
        if d.fecha and d.fecha != fecha:  # el abogado decidió otra fecha: se respeta y queda anotado
            r["ajuste_manual"] = d.fecha.isoformat()
            fecha = d.fecha
        e.calculo = r
    else:
        if not d.fecha:
            raise HTTPException(422, "Indique la fecha.")
        fecha = d.fecha
        if d.tipo != "plazo" or (e.calculo and e.fecha != fecha):
            e.calculo = None if d.tipo != "plazo" else e.calculo
    e.tipo, e.titulo, e.descripcion, e.asunto_id, e.actuacion_id = d.tipo, d.titulo.strip(), _txt(d.descripcion, 5000), d.asunto_id, d.actuacion_id
    e.fecha, e.hora, e.duracion_min = fecha, d.hora, d.duracion_min
    e.lugar, e.enlace, e.prioridad = _txt(d.lugar, 300), _txt(d.enlace, 500), d.prioridad
    e.responsable_id = _usuario(db, d.responsable_id, u)
    e.apoyo_ids = [_usuario(db, x, u) for x in dict.fromkeys(d.apoyo_ids) if x != e.responsable_id]
    e.alertas = base.limpiar_alertas(d.alertas) if d.alertas is not None else None
    if e.validado_en and (antes[0] != e.fecha or antes[1] != e.calculo):
        e.validado_en = e.validado_por_id = None  # cambió la fecha o el cálculo: hay que volver a validar
    e.actualizado_en = m.ahora()


def _conflictos(db: Session, e: m.AgEvento) -> list[str]:
    """Audiencias del mismo responsable el mismo día (solo aviso; no impide guardar)."""
    if e.tipo != "audiencia" or not e.responsable_id:
        return []
    otros = db.scalars(select(m.AgEvento).where(m.AgEvento.organizacion_id == e.organizacion_id, m.AgEvento.id != e.id,
                                                m.AgEvento.tipo == "audiencia", m.AgEvento.estado == "pendiente", m.AgEvento.fecha == e.fecha,
                                                or_(m.AgEvento.responsable_id == e.responsable_id)))
    return [f"{x.titulo}{f' a las {x.hora}' if x.hora else ''}" for x in otros]


@router.post("/eventos", status_code=201)
def crear_evento(d: EventoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    e = m.AgEvento(organizacion_id=u.organizacion_id, creado_por_id=u.id, estado="pendiente")
    _aplicar(db, e, d, u)
    db.add(e)
    db.flush()
    _aud(db, u, "ag_evento_creado", "ag_evento", e.id, request, tipo=e.tipo, fecha=e.fecha.isoformat(), calculado=bool(e.calculo))
    db.commit()
    return {**_evento_dict(db, e), "conflictos": _conflictos(db, e)}


@router.get("/eventos")
def eventos(desde: date | None = None, hasta: date | None = None, responsable_id: int | None = None, asunto_id: int | None = None,
            estado: str = "pendiente", tipo: str | None = None, solo_mios: bool = False, por_validar: bool = False,
            u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    s = select(m.AgEvento).where(m.AgEvento.organizacion_id == u.organizacion_id)
    if estado != "todos":
        s = s.where(m.AgEvento.estado == estado)
    if desde:
        s = s.where(m.AgEvento.fecha >= desde)
    if hasta:
        s = s.where(m.AgEvento.fecha <= hasta)
    if tipo in base.TIPOS_EVENTO:
        s = s.where(m.AgEvento.tipo == tipo)
    if asunto_id:
        s = s.where(m.AgEvento.asunto_id == asunto_id)
    if responsable_id:
        s = s.where(m.AgEvento.responsable_id == responsable_id)
    if por_validar:
        s = s.where(m.AgEvento.tipo == "plazo", m.AgEvento.validado_en.is_(None), m.AgEvento.calculo.is_not(None))
    filas = db.scalars(s.order_by(m.AgEvento.fecha, m.AgEvento.hora.nullsfirst(), m.AgEvento.id).limit(1000)).all()
    if solo_mios:
        filas = [e for e in filas if u.id in base.involucrados(e)]
    nombres, ref = _nombres(db, u.organizacion_id), base.hoy()
    return [_evento_dict(db, e, nombres, ref) for e in filas]


@router.get("/eventos/{eid}")
def ver_evento(eid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    e = _de_org(db, m.AgEvento, eid, u)
    return {**_evento_dict(db, e), "conflictos": _conflictos(db, e)}


@router.patch("/eventos/{eid}")
def editar_evento(eid: int, d: EventoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    e = _de_org(db, m.AgEvento, eid, u)
    if e.estado != "pendiente":
        raise HTTPException(409, "Solo se editan pendientes. Reábralo primero.")
    antes = e.fecha
    _aplicar(db, e, d, u)
    _aud(db, u, "ag_evento_editado", "ag_evento", e.id, request, fecha_antes=antes.isoformat(), fecha=e.fecha.isoformat())
    db.commit()
    return {**_evento_dict(db, e), "conflictos": _conflictos(db, e)}


@router.post("/eventos/{eid}/validar")
def validar(eid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    e = _de_org(db, m.AgEvento, eid, u)
    if e.tipo != "plazo" or e.estado != "pendiente":
        raise HTTPException(409, "Solo se validan plazos pendientes.")
    e.validado_en, e.validado_por_id = m.ahora(), u.id
    _aud(db, u, "ag_plazo_validado", "ag_evento", e.id, request, fecha=e.fecha.isoformat())
    db.commit()
    return _evento_dict(db, e)


class CierreIn(BaseModel):
    nota: str | None = Field(None, max_length=1000)


@router.post("/eventos/{eid}/cumplir")
def cumplir(eid: int, d: CierreIn, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    e = _de_org(db, m.AgEvento, eid, u)
    if u.rol not in ("administrador", "analista") and u.id not in base.involucrados(e):
        raise HTTPException(403, "Su rol no permite esta operación.")
    if e.estado != "pendiente":
        raise HTTPException(409, "Ya no está pendiente.")
    e.estado, e.cumplido_en, e.cumplido_por_id, e.nota_cierre = "cumplido", m.ahora(), u.id, _txt(d.nota, 1000)
    _aud(db, u, "ag_evento_cumplido", "ag_evento", e.id, request, fecha=e.fecha.isoformat(), a_tiempo=base.hoy() <= e.fecha)
    db.commit()
    return _evento_dict(db, e)


@router.post("/eventos/{eid}/cancelar")
def cancelar(eid: int, d: CierreIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    e = _de_org(db, m.AgEvento, eid, u)
    if e.estado != "pendiente":
        raise HTTPException(409, "Ya no está pendiente.")
    if not (d.nota or "").strip() or len(d.nota.strip()) < 5:
        raise HTTPException(422, "Explique por qué se cancela (mínimo 5 caracteres).")
    e.estado, e.cumplido_en, e.cumplido_por_id, e.nota_cierre = "cancelado", m.ahora(), u.id, d.nota.strip()
    _aud(db, u, "ag_evento_cancelado", "ag_evento", e.id, request)
    db.commit()
    return _evento_dict(db, e)


@router.post("/eventos/{eid}/reabrir")
def reabrir(eid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    e = _de_org(db, m.AgEvento, eid, u)
    if e.estado == "pendiente":
        raise HTTPException(409, "Ya está pendiente.")
    e.estado, e.cumplido_en, e.cumplido_por_id = "pendiente", None, None
    _aud(db, u, "ag_evento_reabierto", "ag_evento", e.id, request)
    db.commit()
    return _evento_dict(db, e)


# ------------------------------------------------------------------ vista diaria

@router.get("/hoy")
def vista_hoy(solo_mios: bool = False, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    ref = base.hoy()
    filas = db.scalars(select(m.AgEvento).where(m.AgEvento.organizacion_id == u.organizacion_id, m.AgEvento.estado == "pendiente",
                                                m.AgEvento.fecha <= ref + timedelta(days=7)).order_by(m.AgEvento.fecha, m.AgEvento.hora.nullsfirst())).all()
    if solo_mios:
        filas = [e for e in filas if u.id in base.involucrados(e)]
    nombres = _nombres(db, u.organizacion_id)
    ev = [_evento_dict(db, e, nombres, ref) for e in filas]
    por_validar = db.scalars(select(m.AgEvento).where(m.AgEvento.organizacion_id == u.organizacion_id, m.AgEvento.estado == "pendiente",
                                                      m.AgEvento.tipo == "plazo", m.AgEvento.validado_en.is_(None))).all()
    sin_resp = db.scalars(select(m.AgEvento).where(m.AgEvento.organizacion_id == u.organizacion_id, m.AgEvento.estado == "pendiente",
                                                   m.AgEvento.responsable_id.is_(None))).all()
    avisos = db.scalars(select(m.AgAviso).where(m.AgAviso.usuario_id == u.id, m.AgAviso.leido_en.is_(None))
                        .order_by(m.AgAviso.creado_en.desc()).limit(30)).all()
    cumplidos = db.scalars(select(m.AgEvento).where(m.AgEvento.organizacion_id == u.organizacion_id, m.AgEvento.estado == "cumplido",
                                                    m.AgEvento.cumplido_en >= datetime.combine(ref, datetime.min.time(), tzinfo=base.ZONA))).all()
    return {"fecha": ref.isoformat(),
            "vencidos": [x for x in ev if x["situacion"] == "vencido"], "hoy": [x for x in ev if x["situacion"] == "hoy"],
            "proximos": [x for x in ev if x["situacion"] == "proximo"],
            "por_validar": [_evento_dict(db, e, nombres, ref) for e in por_validar if not solo_mios or u.id in base.involucrados(e)][:50],
            "sin_responsable": [_evento_dict(db, e, nombres, ref) for e in sin_resp][:50],
            "cumplidos_hoy": len(cumplidos),
            "avisos": [{"id": a.id, "nivel": a.nivel, "evento_id": a.evento_id, "creado_en": a.creado_en.isoformat()} for a in avisos]}


@router.get("/contador")
def contador(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    ref = base.hoy()
    filas = db.scalars(select(m.AgEvento).where(m.AgEvento.organizacion_id == u.organizacion_id, m.AgEvento.estado == "pendiente",
                                                m.AgEvento.fecha <= ref)).all()
    return {"total": sum(1 for e in filas if u.id in base.involucrados(e) or (u.rol == "administrador" and e.fecha < ref))}


@router.post("/avisos/leidos")
def avisos_leidos(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    db.query(m.AgAviso).filter(m.AgAviso.usuario_id == u.id, m.AgAviso.leido_en.is_(None)).update({"leido_en": m.ahora()}, synchronize_session=False)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ preferencias y calendario externo

def _pref(db: Session, u: m.Usuario) -> m.AgPreferencia:
    p = db.scalar(select(m.AgPreferencia).where(m.AgPreferencia.usuario_id == u.id))
    if p is None:
        p = m.AgPreferencia(usuario_id=u.id, resumen_diario=True, alertas_correo=True, feed_detalle="reservado")
        db.add(p)
        db.flush()
    return p


def _pref_dict(p: m.AgPreferencia) -> dict:
    return {"resumen_diario": p.resumen_diario, "alertas_correo": p.alertas_correo, "feed_activo": bool(p.feed_token_hash),
            "feed_detalle": p.feed_detalle, "feed_creado_en": p.feed_creado_en.isoformat() if p.feed_creado_en else None}


class PrefIn(BaseModel):
    resumen_diario: bool
    alertas_correo: bool
    feed_detalle: str = "reservado"


@router.get("/preferencias")
def ver_pref(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    p = _pref(db, u)
    db.commit()
    return _pref_dict(p)


@router.put("/preferencias")
def guardar_pref(d: PrefIn, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    if d.feed_detalle not in ("reservado", "completo"):
        raise HTTPException(422, "Opción inválida.")
    p = _pref(db, u)
    p.resumen_diario, p.alertas_correo, p.feed_detalle = d.resumen_diario, d.alertas_correo, d.feed_detalle
    db.commit()
    return _pref_dict(p)


@router.post("/preferencias/feed")
def nuevo_feed(request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Genera un enlace privado para suscribirse desde Google Calendar u Outlook. Se muestra UNA vez."""
    p = _pref(db, u)
    token = secrets.token_urlsafe(32)
    p.feed_token_hash, p.feed_creado_en = hashlib.sha256(token.encode()).hexdigest(), m.ahora()
    _aud(db, u, "ag_feed_generado", "ag_preferencia", p.id, request)
    db.commit()
    return {**_pref_dict(p), "url": f"{ajustes().url_publica.rstrip('/')}/api/agenda-feed/{token}.ics"}


@router.delete("/preferencias/feed")
def quitar_feed(request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    p = _pref(db, u)
    p.feed_token_hash = p.feed_creado_en = None
    _aud(db, u, "ag_feed_revocado", "ag_preferencia", p.id, request)
    db.commit()
    return _pref_dict(p)


# ------------------------------------------------------------------ exportaciones

def ics(eventos: list[m.AgEvento], db: Session, detalle: str = "completo") -> str:
    def esc(t: str) -> str:
        return (t or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    ahora = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    host = ajustes().url_publica.split("://")[-1].split("/")[0] or "nomira"
    lineas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Nomira//Agenda Juridica//ES", "CALSCALE:GREGORIAN",
              "X-WR-CALNAME:Nomira · Agenda", "X-WR-TIMEZONE:America/Mexico_City"]
    for e in eventos:
        a = db.get(m.AgAsunto, e.asunto_id) if e.asunto_id else None
        if detalle == "completo":
            titulo = f"{base.TIPOS_EVENTO[e.tipo]}: {e.titulo}"
            desc = "\n".join(x for x in [f"Asunto: {a.titulo} {a.numero or ''}".strip() if a else None, a.tribunal if a else None,
                                         e.descripcion, "Cálculo sin validar" if base.pendientes_de_validar(e) and e.calculo else None] if x)
        else:  # sin nombres: los calendarios externos no son tan privados como Nomira
            titulo = f"{base.TIPOS_EVENTO[e.tipo]}{f' · {a.numero}' if a and a.numero else ''} (Nomira)"
            desc = "Detalles en Nomira."
        lineas += ["BEGIN:VEVENT", f"UID:ag-{e.id}@{host}", f"DTSTAMP:{ahora}"]
        if e.hora:
            ini = datetime.combine(e.fecha, datetime.strptime(e.hora, "%H:%M").time())
            fin = ini + timedelta(minutes=e.duracion_min or 60)
            lineas += [f"DTSTART;TZID=America/Mexico_City:{ini:%Y%m%dT%H%M%S}", f"DTEND;TZID=America/Mexico_City:{fin:%Y%m%dT%H%M%S}"]
        else:
            lineas += [f"DTSTART;VALUE=DATE:{e.fecha:%Y%m%d}", f"DTEND;VALUE=DATE:{e.fecha + timedelta(days=1):%Y%m%d}"]
        lineas += [f"SUMMARY:{esc(titulo)}", f"DESCRIPTION:{esc(desc)}"]
        if detalle == "completo" and (e.lugar or e.enlace):
            lineas.append(f"LOCATION:{esc(e.lugar or e.enlace)}")
        lineas += [f"URL:{ajustes().url_publica.rstrip('/')}/agenda/eventos/{e.id}", "BEGIN:VALARM", "ACTION:DISPLAY",
                   f"DESCRIPTION:{esc(titulo)}", "TRIGGER:-PT1H" if e.hora else "TRIGGER:-PT15H", "END:VALARM", "END:VEVENT"]
    lineas.append("END:VCALENDAR")
    return "\r\n".join(lineas) + "\r\n"


@router.get("/eventos/{eid}/calendario.ics")
def evento_ics(eid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    e = _de_org(db, m.AgEvento, eid, u)
    return Response(ics([e], db), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="agenda-{e.id}.ics"', "Cache-Control": "no-store"})


@router.get("/exportar.csv")
def exportar(desde: date | None = None, hasta: date | None = None, request: Request = None, u: m.Usuario = Depends(usuario_actual),
             db: Session = Depends(get_db)):
    desde = desde or base.hoy() - timedelta(days=30)
    hasta = hasta or base.hoy() + timedelta(days=90)
    filas = eventos(desde, hasta, None, None, "todos", None, False, False, u, db)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Fecha", "Hora", "Tipo", "Título", "Asunto", "Número", "Tribunal", "Responsable", "Prioridad", "Estado", "Validado por"])
    for x in filas:
        a = x["asunto"] or {}
        w.writerow([x["fecha"], x["hora"] or "", x["tipo_texto"], x["titulo"], a.get("titulo", ""), a.get("numero") or "", a.get("tribunal") or "",
                    x["responsable"] or "", x["prioridad"], x["estado"], x["validado_por"] or ""])
    _aud(db, u, "ag_exportado", "ag_evento", None, request, filas=len(filas))
    db.commit()
    return Response("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="agenda-{desde}-{hasta}.csv"', "Cache-Control": "no-store"})
