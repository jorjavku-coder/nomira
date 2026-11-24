"""Bolsa de trabajo pública: portal de Nomira, página por despacho, postulación y contestar pruebas con enlace."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import ip_cliente
from ..freno import Ventana
from ..services.bolsa import base as bt, pruebas as pb
from .bolsa import vacante_dict

router = APIRouter(tags=["Bolsa de trabajo (pública)"])
_postulaciones_ip = Ventana(10, 3600)
_fallos_ip = Ventana(30, 900)
POR_PAGINA = 20


def _visibles(db: Session) -> set[int]:
    orgs = set(db.scalars(select(m.BtVacante.organizacion_id).where(m.BtVacante.estado == "publicada").distinct()))
    return {o for o in orgs if bt.org_visible(db, o)}


def _con_despacho(db: Session, v: m.BtVacante) -> dict:
    p = db.scalar(select(m.BtPerfil).where(m.BtPerfil.organizacion_id == v.organizacion_id))
    return {**vacante_dict(v), "despacho": {"nombre": p.nombre_publico, "codigo": p.codigo, "ciudad": p.ciudad} if p else None}


@router.get("/api/empleos")
def portal(texto: str | None = None, area: str | None = None, modalidad: str | None = None, estado: str | None = None, pagina: int = 1,
           db: Session = Depends(get_db)):
    q = select(m.BtVacante).where(m.BtVacante.estado == "publicada", m.BtVacante.en_portal.is_(True),
                                  m.BtVacante.organizacion_id.in_(_visibles(db) or {0}))
    if area in bt.AREAS:
        q = q.where(m.BtVacante.area == area)
    if modalidad in bt.MODALIDADES:
        q = q.where(m.BtVacante.modalidad == modalidad)
    if estado in bt.ESTADOS_MX:
        q = q.where(or_(m.BtVacante.estado_republica == estado, m.BtVacante.modalidad == "remoto"))
    t = re.sub(r"[%_\\]", "", (texto or "").strip())[:80]
    if t:
        q = q.where(or_(m.BtVacante.titulo.ilike(f"%{t}%"), m.BtVacante.descripcion.ilike(f"%{t}%"), m.BtVacante.ciudad.ilike(f"%{t}%")))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    pagina = max(1, min(pagina, 50))
    vs = db.scalars(q.order_by(m.BtVacante.publicada_en.desc()).offset((pagina - 1) * POR_PAGINA).limit(POR_PAGINA)).all()
    return {"vacantes": [_con_despacho(db, v) for v in vs], "total": total, "pagina": pagina, "por_pagina": POR_PAGINA,
            "areas": bt.AREAS, "modalidades": bt.MODALIDADES, "estados_mx": bt.ESTADOS_MX}


@router.get("/api/empleos/despacho/{codigo}")
def despacho(codigo: str, db: Session = Depends(get_db)):
    p = db.scalar(select(m.BtPerfil).where(m.BtPerfil.codigo == codigo))
    if not p or not bt.org_visible(db, p.organizacion_id):
        raise HTTPException(404, "No encontramos esta página de empleos.")
    vs = db.scalars(select(m.BtVacante).where(m.BtVacante.organizacion_id == p.organizacion_id, m.BtVacante.estado == "publicada")
                    .order_by(m.BtVacante.publicada_en.desc())).all()
    return {"despacho": {"nombre": p.nombre_publico, "descripcion": p.descripcion, "ciudad": p.ciudad, "sitio_web": p.sitio_web, "codigo": p.codigo},
            "vacantes": [vacante_dict(v) for v in vs]}


def _vacante_publica(db: Session, codigo: str) -> m.BtVacante:
    v = db.scalar(select(m.BtVacante).where(m.BtVacante.codigo == codigo))
    if not v or v.estado not in ("publicada", "pausada", "cerrada") or not bt.org_visible(db, v.organizacion_id):
        raise HTTPException(404, "Esta vacante no existe o ya no está disponible.")
    return v


@router.get("/api/empleos/vacante/{codigo}")
def vacante(codigo: str, db: Session = Depends(get_db)):
    v = _vacante_publica(db, codigo)
    p = db.scalar(select(m.BtPerfil).where(m.BtPerfil.organizacion_id == v.organizacion_id))
    return {**_con_despacho(db, v), "recibe": v.estado == "publicada", "correo_privacidad": p.correo_privacidad if p else None,
            "experiencia": bt.EXPERIENCIA}


@router.post("/api/empleos/vacante/{codigo}/postular", status_code=201)
async def postular(codigo: str, request: Request, nombre: str = Form(..., max_length=200), email: str = Form(..., max_length=254),
                   telefono: str | None = Form(None, max_length=30), ciudad: str | None = Form(None, max_length=120),
                   cedula: str | None = Form(None, max_length=20), experiencia: str | None = Form(None), mensaje: str | None = Form(None, max_length=4000),
                   acepto: bool = Form(False), sitio_web: str | None = Form(None), cv: UploadFile | None = File(None),
                   db: Session = Depends(get_db)):
    ip = ip_cliente(request) or "?"
    if _postulaciones_ip.excedida(ip):
        raise HTTPException(429, "Recibimos muchas postulaciones desde tu conexión. Intenta más tarde.")
    _postulaciones_ip.registrar(ip)
    v = _vacante_publica(db, codigo)
    if v.estado != "publicada":
        raise HTTPException(409, "Esta vacante ya no recibe postulaciones.")
    if sitio_web:  # campo trampa: solo lo llenan los robots
        return {"ok": True}
    if not acepto:
        raise HTTPException(422, "Para postularte necesitas aceptar el aviso de privacidad.")
    nombre_l = bt.txt(nombre, 200)
    email_l = (email or "").strip().lower()
    if not nombre_l or len(nombre_l) < 3:
        raise HTTPException(422, "Escribe tu nombre completo.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email_l):
        raise HTTPException(422, "Escribe un correo válido.")
    if experiencia and experiencia not in bt.EXPERIENCIA:
        raise HTTPException(422, "Experiencia no válida.")
    if cedula and not re.fullmatch(r"\d{7,8}", cedula.strip()):
        raise HTTPException(422, "La cédula profesional son 7 u 8 dígitos.")
    existente = db.scalar(select(m.BtCandidato).where(m.BtCandidato.vacante_id == v.id, func.lower(m.BtCandidato.email) == email_l))
    if existente:
        return {"ok": True, "repetida": True}
    archivo = nombre_cv = None
    tamano = None
    if cv is not None and cv.filename:
        contenido = await cv.read(bt.MAX_CV + 1)
        if len(contenido) > bt.MAX_CV:
            raise HTTPException(413, "Tu CV pesa más de 5 MB.")
        try:
            archivo, nombre_cv = bt.guardar_cv(v.organizacion_id, v.id, cv.filename, contenido)
        except ValueError as e:
            raise HTTPException(422, str(e))
        tamano = len(contenido)
    c = m.BtCandidato(organizacion_id=v.organizacion_id, vacante_id=v.id, nombre=nombre_l, email=email_l, telefono=bt.txt(telefono, 30),
                      ciudad=bt.txt(ciudad, 120), cedula=(cedula or "").strip() or None, experiencia=experiencia or None, mensaje=bt.txt(mensaje, 4000),
                      cv_archivo=archivo, cv_nombre=nombre_cv, cv_tamano=tamano)
    db.add(c)
    db.add(m.Auditoria(organizacion_id=v.organizacion_id, accion="bolsa_postulacion", entidad="bt_vacante", entidad_id=v.id, detalle={"cv": bool(archivo)}))
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ contestar una prueba

def _aplicacion(db: Session, token: str, request: Request) -> m.BtAplicacion:
    ip = ip_cliente(request) or "?"
    if _fallos_ip.excedida(ip):
        raise HTTPException(429, "Demasiados intentos. Espera unos minutos.")
    a = db.scalar(select(m.BtAplicacion).where(m.BtAplicacion.token_hash == bt.huella(token))) if len(token) < 100 else None
    if not a:
        _fallos_ip.registrar(ip)
        raise HTTPException(404, "Este enlace no es válido.")
    return a


def _estado(a: m.BtAplicacion) -> str:
    if a.estado in ("enviada", "en_curso") and a.vence_en < datetime.now(timezone.utc):
        return "vencida"
    return a.estado


@router.get("/api/prueba/{token}")
def ver(token: str, request: Request, db: Session = Depends(get_db)):
    a = _aplicacion(db, token, request)
    c = db.get(m.BtCandidato, a.candidato_id)
    perfil = db.scalar(select(m.BtPerfil).where(m.BtPerfil.organizacion_id == a.organizacion_id))
    estado = _estado(a)
    x = {"estado": estado, "candidato": c.nombre.split(" ")[0] if c else "", "despacho": perfil.nombre_publico if perfil else "",
         "correo_privacidad": perfil.correo_privacidad if perfil else None, "vence_en": a.vence_en.isoformat()}
    p = bt.prueba_def(db, a.organizacion_id, a.prueba)
    if p and estado in ("enviada", "en_curso"):
        vista = pb.para_candidato(p)
        x["prueba"] = vista if estado == "en_curso" else {k: vista[k] for k in ("nombre", "instrucciones", "minutos", "tipo")} | {"n": len(vista["preguntas"])}
        x["iniciada_en"] = a.iniciada_en.isoformat() if a.iniciada_en else None
    return x


class IniciarIn(BaseModel):
    acepto: bool


@router.post("/api/prueba/{token}/iniciar")
def iniciar(token: str, d: IniciarIn, request: Request, db: Session = Depends(get_db)):
    a = _aplicacion(db, token, request)
    if _estado(a) not in ("enviada", "en_curso"):
        raise HTTPException(409, "Esta prueba ya no está disponible.")
    if not d.acepto:
        raise HTTPException(422, "Para contestar necesitas aceptar el uso de tus respuestas en este proceso de selección.")
    if a.estado == "enviada":
        ahora = datetime.now(timezone.utc)
        a.estado, a.iniciada_en, a.consentimiento_en = "en_curso", ahora, ahora
        db.commit()
    return ver(token, request, db)


class RespuestasIn(BaseModel):
    respuestas: list[int | str | None] = Field(max_length=200)


@router.post("/api/prueba/{token}/responder")
def responder(token: str, d: RespuestasIn, request: Request, db: Session = Depends(get_db)):
    a = _aplicacion(db, token, request)
    a = db.scalar(select(m.BtAplicacion).where(m.BtAplicacion.id == a.id).with_for_update())
    if a.estado != "en_curso" or _estado(a) == "vencida":
        raise HTTPException(409, "Esta prueba ya no recibe respuestas.")
    p = bt.prueba_def(db, a.organizacion_id, a.prueba)
    if not p:
        raise HTTPException(409, "Esta prueba ya no está disponible.")
    respuestas = [r if isinstance(r, int) else (str(r)[:4000] if r is not None else None) for r in d.respuestas][: len(p["preguntas"])]
    resultado = pb.calificar(p, respuestas)
    ahora = datetime.now(timezone.utc)
    if p.get("minutos") and a.iniciada_en:
        usados = (ahora - a.iniciada_en).total_seconds() / 60
        resultado["minutos_usados"] = round(usados, 1)
        resultado["fuera_de_tiempo"] = usados > p["minutos"] * 1.1 + 1
    a.respuestas, a.resultado, a.estado, a.terminada_en = {"respuestas": respuestas}, resultado, "terminada", ahora
    db.add(m.Auditoria(organizacion_id=a.organizacion_id, accion="bolsa_prueba_contestada", entidad="bt_candidato", entidad_id=a.candidato_id,
                       detalle={"aplicacion": a.id}))
    db.commit()
    return {"ok": True}  # el resultado solo lo ve el despacho
