"""Nomira Connect (panel del despacho): plantillas, seguimiento de cada asunto, enlaces del cliente y mensajes.

Todo se filtra por la organización del usuario. Las rutas del cliente están en connect_publico.py.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import auditar, obtener, puede_editar, usuario_actual
from ..services.agenda.base import MATERIAS
from ..services.connect import base as cb
from ..services.connect import plantillas as pl
from ..services.connect import portal

router = APIRouter(prefix="/api/connect", tags=["Nomira Connect"])

MOTIVOS = {"seguimiento": "Consulta de seguimiento", "llamada": "Pide una llamada", "cita": "Pide una cita",
           "documentos": "Envío de documentos", "honorarios": "Aclaración de honorarios", "otro": "Otro"}


def _seg(db: Session, sid: int, u: m.Usuario) -> tuple[m.CnSeguimiento, m.AgAsunto]:
    s = obtener(db, m.CnSeguimiento, sid, u)
    return s, db.get(m.AgAsunto, s.asunto_id)


# ------------------------------------------------------------------ resumen

@router.get("/contador")
def contador(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Para el menú: mensajes de clientes sin atender."""
    return {"mensajes": db.scalar(select(func.count(m.CnMensaje.id)).where(m.CnMensaje.organizacion_id == u.organizacion_id,
                                                                         m.CnMensaje.autor == "cliente", m.CnMensaje.estado == "nuevo")) or 0}


@router.get("/resumen")
def resumen(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    org = u.organizacion_id
    segs = {s.asunto_id: s for s in db.scalars(select(m.CnSeguimiento).where(m.CnSeguimiento.organizacion_id == org))}
    asuntos = db.scalars(select(m.AgAsunto).where(m.AgAsunto.organizacion_id == org, m.AgAsunto.estado != "archivado")
                         .order_by(m.AgAsunto.titulo)).all()
    clientes = {c.id: c.nombre for c in db.scalars(select(m.CrCliente).where(m.CrCliente.organizacion_id == org))}
    nombres = {x.id: x.nombre for x in db.scalars(select(m.Usuario).where(m.Usuario.organizacion_id == org))}
    actuales = {}
    if segs:
        for e in db.scalars(select(m.CnEtapa).where(m.CnEtapa.seguimiento_id.in_([s.id for s in segs.values()]),
                                                   m.CnEtapa.estado.in_(("actual", "atencion", "incidencia", "suspendida")))
                            .order_by(m.CnEtapa.orden)):
            actuales.setdefault(e.seguimiento_id, e)
    filas = []
    for a in asuntos:
        s = segs.get(a.id)
        e = actuales.get(s.id) if s else None
        filas.append({"asunto_id": a.id, "asunto": a.titulo, "numero": a.numero, "cliente": clientes.get(a.cr_cliente_id),
                      "cliente_id": a.cr_cliente_id, "materia": MATERIAS.get(a.materia, a.materia), "responsable": nombres.get(a.responsable_id),
                      "seguimiento_id": s.id if s else None, "visible": bool(s and s.visible_cliente), "estado": s.estado if s else None,
                      "etapa": e.nombre if e else None, "etapa_estado": e.estado if e else None,
                      "dias_sin_actualizar": cb.dias_sin_actualizar(s) if s else None})
    nuevos = db.scalar(select(func.count(m.CnMensaje.id)).where(m.CnMensaje.organizacion_id == org, m.CnMensaje.autor == "cliente",
                                                                m.CnMensaje.estado == "nuevo")) or 0
    con = [f for f in filas if f["seguimiento_id"]]
    return {"asuntos": filas, "mensajes_nuevos": nuevos,
            "cifras": {"con_seguimiento": len(con), "publicados": sum(1 for f in con if f["visible"]),
                       "sin_actualizar_15": sum(1 for f in con if (f["dias_sin_actualizar"] or 0) >= 15 and f["estado"] == "activo"),
                       "requieren_cliente": sum(1 for f in con if f["etapa_estado"] == "atencion")},
            "especialidades": pl.ESPECIALIDADES, "materias": MATERIAS}


# ------------------------------------------------------------------ plantillas

class Plantilla(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    especialidad: str = Field(max_length=40)
    etapas: list[dict] = Field(min_length=1, max_length=40)


@router.get("/plantillas")
def plantillas(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    propias = db.scalars(select(m.CnPlantilla).where(m.CnPlantilla.organizacion_id == u.organizacion_id).order_by(m.CnPlantilla.nombre))
    return {"propias": [{"id": p.id, "nombre": p.nombre, "especialidad": p.especialidad, "etapas": p.etapas} for p in propias],
            "base": [{"clave": k, "nombre": v["nombre"], "nota": v.get("nota"), "etapas": v["etapas"]} for k, v in pl.BASE.items()]}


@router.post("/plantillas", status_code=201)
def crear_plantilla(d: Plantilla, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    etapas = pl.limpiar_etapas(d.etapas)
    if not etapas:
        raise HTTPException(422, "Agregue al menos una etapa con nombre.")
    p = m.CnPlantilla(organizacion_id=u.organizacion_id, nombre=d.nombre.strip(), especialidad=d.especialidad, etapas=etapas, creado_por_id=u.id)
    db.add(p)
    db.flush()
    auditar(db, u, "cn_plantilla_creada", "cn_plantilla", p.id, {"etapas": len(etapas)}, request)
    db.commit()
    return {"id": p.id}


@router.put("/plantillas/{pid}")
def editar_plantilla(pid: int, d: Plantilla, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    p = obtener(db, m.CnPlantilla, pid, u)
    etapas = pl.limpiar_etapas(d.etapas)
    if not etapas:
        raise HTTPException(422, "Agregue al menos una etapa con nombre.")
    p.nombre, p.especialidad, p.etapas = d.nombre.strip(), d.especialidad, etapas
    auditar(db, u, "cn_plantilla_editada", "cn_plantilla", p.id, {"etapas": len(etapas)}, request)
    db.commit()
    return {"ok": True}


@router.delete("/plantillas/{pid}")
def borrar_plantilla(pid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    p = obtener(db, m.CnPlantilla, pid, u)
    db.delete(p)  # los asuntos que ya la usan conservan sus etapas (son copia)
    auditar(db, u, "cn_plantilla_borrada", "cn_plantilla", pid, {}, request)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ seguimiento de un asunto

class NuevoSeguimiento(BaseModel):
    asunto_id: int | None = None
    # o un asunto nuevo:
    titulo: str | None = Field(None, max_length=200)
    numero: str | None = Field(None, max_length=80)
    cliente_id: int | None = None
    materia: str | None = None
    # plantilla: de fábrica (clave) o propia (id)
    base: str | None = None
    plantilla_id: int | None = None


@router.post("/seguimientos", status_code=201)
def crear_seguimiento(d: NuevoSeguimiento, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    if d.asunto_id:
        a = obtener(db, m.AgAsunto, d.asunto_id, u)
    else:
        if not (d.titulo or "").strip():
            raise HTTPException(422, "Escriba el nombre del asunto.")
        if d.cliente_id:
            obtener(db, m.CrCliente, d.cliente_id, u)
        a = m.AgAsunto(organizacion_id=u.organizacion_id, titulo=d.titulo.strip(), numero=(d.numero or "").strip() or None,
                       cr_cliente_id=d.cliente_id, materia=d.materia if d.materia in MATERIAS else "otra", jurisdiccion="federal",
                       responsable_id=u.id, estado="activo", creado_por_id=u.id)
        db.add(a)
        db.flush()
    if db.scalar(select(m.CnSeguimiento.id).where(m.CnSeguimiento.asunto_id == a.id)):
        raise HTTPException(409, "Este asunto ya tiene seguimiento.")
    if d.plantilla_id:
        p = obtener(db, m.CnPlantilla, d.plantilla_id, u)
        nombre, esp, etapas = p.nombre, p.especialidad, p.etapas
    elif d.base in pl.BASE:
        nombre, esp, etapas = pl.BASE[d.base]["nombre"], d.base, pl.BASE[d.base]["etapas"]
    else:
        raise HTTPException(422, "Elija una plantilla.")
    s = cb.crear(db, a, nombre, esp, etapas, u)
    auditar(db, u, "cn_seguimiento_creado", "cn_seguimiento", s.id, {"asunto_id": a.id, "plantilla": nombre}, request)
    db.commit()
    return {"id": s.id, "asunto_id": a.id}


@router.get("/seguimientos/{sid}")
def ver_seguimiento(sid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    s, a = _seg(db, sid, u)
    return cb.panel(db, s, a)


class Ajustes(BaseModel):
    visible_cliente: bool | None = None
    mostrar_audiencias: bool | None = None
    mostrar_pagos: bool | None = None
    mensaje_publico: str | None = Field(None, max_length=1000)
    accion_cliente: str | None = Field(None, max_length=500)
    estado: str | None = None  # activo | suspendido | cerrado
    cliente_id: int | None = None  # vincula el asunto con un cliente del directorio


@router.put("/seguimientos/{sid}")
def ajustar(sid: int, d: Ajustes, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    s, a = _seg(db, sid, u)
    cambios = d.model_dump(exclude_unset=True)
    if "cliente_id" in cambios:
        cid = cambios.pop("cliente_id")
        if cid:
            obtener(db, m.CrCliente, cid, u)
        elif s.visible_cliente:
            raise HTTPException(409, "Oculte el seguimiento antes de quitar el cliente.")
        if a.cr_cliente_id != cid:
            a.cr_cliente_id = cid
            auditar(db, u, "cn_cliente_vinculado", "ag_asunto", a.id, {"cliente_id": cid}, request)
    if "estado" in cambios and cambios["estado"] not in ("activo", "suspendido", "cerrado"):
        raise HTTPException(422, "Estado no válido.")
    if "visible_cliente" in cambios and cambios["visible_cliente"] and not a.cr_cliente_id:
        raise HTTPException(409, "Primero vincule el asunto con un cliente del directorio.")
    for k in ("mensaje_publico", "accion_cliente"):
        if k in cambios:
            cambios[k] = (cambios[k] or "").strip() or None
    previo = {k: getattr(s, k) for k in cambios}
    for k, v in cambios.items():
        setattr(s, k, v)
    if "mensaje_publico" in cambios and cambios["mensaje_publico"] and cambios["mensaje_publico"] != previo["mensaje_publico"]:
        cb.evento(db, s, "aviso", "Mensaje de su abogado", cambios["mensaje_publico"], True, u)
    if "accion_cliente" in cambios and cambios["accion_cliente"] and cambios["accion_cliente"] != previo["accion_cliente"]:
        cb.evento(db, s, "aviso", "Necesitamos algo de usted", cambios["accion_cliente"], True, u)
    if "estado" in cambios and cambios["estado"] != previo["estado"]:
        txt = {"suspendido": "El asunto está suspendido temporalmente", "cerrado": "El asunto concluyó", "activo": "El asunto se reactivó"}[s.estado]
        cb.evento(db, s, "estado", txt, None, True, u)
    auditar(db, u, "cn_seguimiento_ajustado", "cn_seguimiento", s.id, {k: (v if isinstance(v, bool) or k == "estado" else "editado")
                                                                         for k, v in cambios.items()}, request)
    db.commit()
    return cb.panel(db, s, a)


class Mover(BaseModel):
    etapa_id: int
    estado: str  # actual | completada | atencion | incidencia | suspendida | pendiente | omitida
    nota_publica: str | None = Field(None, max_length=500)
    nota_interna: str | None = Field(None, max_length=1000)
    avisar: bool = True  # registrar en el historial visible para el cliente


@router.post("/seguimientos/{sid}/etapa")
def mover(sid: int, d: Mover, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    s, a = _seg(db, sid, u)
    e = db.get(m.CnEtapa, d.etapa_id)
    if not e or e.seguimiento_id != s.id:
        raise HTTPException(404, "No encontrado.")
    if d.estado not in cb.ESTADOS_PANEL:
        raise HTTPException(422, "Estado no válido.")
    previo = e.estado
    if d.nota_publica is not None:
        e.nota_publica = d.nota_publica.strip() or None
    if d.nota_interna is not None:
        e.nota_interna = d.nota_interna.strip() or None
    anterior = None
    if d.estado == "actual":
        anterior = cb.marcar_actual(db, s, e, u)
    else:
        e.estado = d.estado
        e.fecha = date.today() if d.estado in ("completada", "atencion", "incidencia", "suspendida") else (None if d.estado == "pendiente" else e.fecha)
        e.actualizado_por_id, e.actualizado_en = u.id, m.ahora()
    if d.avisar and (previo != d.estado or d.nota_publica):
        titulos = {"actual": f"Nueva etapa: {e.nombre}", "completada": f"Etapa completada: {e.nombre}",
                   "atencion": f"Necesitamos algo de usted: {e.nombre}", "incidencia": f"Hay una incidencia en: {e.nombre}",
                   "suspendida": f"Etapa suspendida temporalmente: {e.nombre}", "pendiente": f"Etapa por realizar: {e.nombre}",
                   "omitida": f"Esta etapa no aplica: {e.nombre}"}
        detalle = e.nota_publica or (e.explicacion if d.estado == "actual" else None)
        if anterior and d.estado == "actual":
            detalle = f"Etapa anterior: {anterior}." + (f" {detalle}" if detalle else "")
        cb.evento(db, s, "etapa", titulos[d.estado], detalle, True, u)
    auditar(db, u, "cn_etapa_cambiada", "cn_etapa", e.id, {"seguimiento_id": s.id, "de": previo, "a": d.estado}, request)
    db.commit()
    return cb.panel(db, s, a)


class Etapas(BaseModel):
    etapas: list[dict] = Field(min_length=1, max_length=40)  # [{id?, nombre, explicacion, opcional}] en el orden deseado


@router.put("/seguimientos/{sid}/etapas")
def editar_etapas(sid: int, d: Etapas, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """Personaliza las etapas de ESTE asunto (no cambia la plantilla ni otros asuntos)."""
    s, a = _seg(db, sid, u)
    actuales = {e.id: e for e in cb.etapas_de(db, s)}
    vistos = set()
    for i, x in enumerate(d.etapas):
        nombre = str(x.get("nombre") or "").strip()[:120]
        if not nombre:
            continue
        e = actuales.get(int(x["id"])) if str(x.get("id") or "").isdigit() else None
        if e is None:
            e = m.CnEtapa(organizacion_id=s.organizacion_id, seguimiento_id=s.id, estado="pendiente")
            db.add(e)
        e.orden, e.nombre = i, nombre
        e.explicacion = (str(x.get("explicacion") or "").strip()[:500]) or None
        e.opcional = bool(x.get("opcional"))
        if e.id:
            vistos.add(e.id)
    for eid, e in actuales.items():
        if eid not in vistos:
            db.delete(e)
    db.flush()
    if not cb.etapas_de(db, s):
        raise HTTPException(422, "Deje al menos una etapa.")
    auditar(db, u, "cn_etapas_editadas", "cn_seguimiento", s.id, {"etapas": len(d.etapas)}, request)
    db.commit()
    return cb.panel(db, s, a)


class Movimiento(BaseModel):
    fecha: date
    texto: str = Field(min_length=3, max_length=500)


@router.post("/seguimientos/{sid}/movimiento")
def movimiento(sid: int, d: Movimiento, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """Último movimiento judicial confirmado, redactado por el abogado para el cliente."""
    s, a = _seg(db, sid, u)
    if d.fecha > date.today():
        raise HTTPException(422, "La fecha del movimiento no puede ser futura.")
    s.ultimo_movimiento_fecha, s.ultimo_movimiento_texto = d.fecha, d.texto.strip()
    cb.evento(db, s, "movimiento", "Nuevo movimiento en su expediente", d.texto.strip(), True, u)
    auditar(db, u, "cn_movimiento", "cn_seguimiento", s.id, {"fecha": d.fecha.isoformat()}, request)
    db.commit()
    return cb.panel(db, s, a)


@router.post("/seguimientos/{sid}/revisado")
def revisado(sid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """El abogado registra que revisó el expediente hoy (la revisión se distingue del último movimiento judicial)."""
    s, a = _seg(db, sid, u)
    s.ultima_revision_en, s.ultima_revision_por_id = m.ahora(), u.id
    cb.evento(db, s, "revision", "Su abogado revisó el expediente", None, True, u)
    auditar(db, u, "cn_revisado", "cn_seguimiento", s.id, {}, request)
    db.commit()
    return cb.panel(db, s, a)


@router.delete("/seguimientos/{sid}")
def borrar_seguimiento(sid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    s, _ = _seg(db, sid, u)
    db.delete(s)  # el asunto de la Agenda se conserva
    auditar(db, u, "cn_seguimiento_borrado", "cn_seguimiento", sid, {}, request)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ enlaces del cliente

@router.get("/clientes/{cid}/enlaces")
def enlaces(cid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = obtener(db, m.CrCliente, cid, u)
    return {"cliente": c.nombre, "email": bool(c.email),
            "enlaces": [{"id": x.id, "pista": x.token_pista, "estado": portal.estado(x), "requiere_codigo": x.requiere_codigo,
                         "expira_en": x.expira_en.isoformat(), "visitas": x.visitas,
                         "ultimo_uso_en": x.ultimo_uso_en.isoformat() if x.ultimo_uso_en else None}
                        for x in db.scalars(select(m.CnAcceso).where(m.CnAcceso.cliente_id == c.id).order_by(m.CnAcceso.id.desc()))]}


class NuevoEnlace(BaseModel):
    dias: int = Field(30, ge=1, le=180)


@router.post("/clientes/{cid}/enlaces", status_code=201)
def nuevo_enlace(cid: int, d: NuevoEnlace, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = obtener(db, m.CrCliente, cid, u)
    a, token, url = portal.nuevo_acceso(db, c, u, d.dias)
    auditar(db, u, "cn_enlace_creado", "cr_cliente", c.id, {"acceso_id": a.id, "dias": d.dias, "codigo": a.requiere_codigo}, request)
    db.commit()
    return {"url": url, "requiere_codigo": a.requiere_codigo, "expira_en": a.expira_en.isoformat()}


@router.post("/enlaces/{aid}/revocar")
def revocar(aid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = obtener(db, m.CnAcceso, aid, u)
    a.revocado_en = a.revocado_en or m.ahora()
    auditar(db, u, "cn_enlace_revocado", "cr_cliente", a.cliente_id, {"acceso_id": a.id}, request)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ mensajes

@router.get("/mensajes")
def bandeja(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    org = u.organizacion_id
    hilos: dict[int, dict] = {}
    for x in db.scalars(select(m.CnMensaje).where(m.CnMensaje.organizacion_id == org).order_by(m.CnMensaje.creado_en.desc()).limit(2000)):
        h = hilos.setdefault(x.cliente_id, {"cliente_id": x.cliente_id, "ultimo": x.texto[:140], "fecha": x.creado_en.isoformat(),
                                            "autor": x.autor, "nuevos": 0, "motivo": None})
        if x.autor == "cliente" and x.estado == "nuevo":
            h["nuevos"] += 1
            h["motivo"] = h["motivo"] or MOTIVOS.get(x.motivo or "")
    nombres = {c.id: c.nombre for c in db.scalars(select(m.CrCliente).where(m.CrCliente.id.in_(list(hilos) or [0])))}
    filas = [{**h, "cliente": nombres.get(cid, "Cliente")} for cid, h in hilos.items()]
    filas = sorted([f for f in filas if f["nuevos"]], key=lambda h: h["fecha"], reverse=True) + \
        sorted([f for f in filas if not f["nuevos"]], key=lambda h: h["fecha"], reverse=True)
    return {"hilos": filas, "motivos": MOTIVOS}


@router.get("/mensajes/{cid}")
def hilo(cid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    c = obtener(db, m.CrCliente, cid, u)
    nombres = {x.id: x.nombre for x in db.scalars(select(m.Usuario).where(m.Usuario.organizacion_id == u.organizacion_id))}
    asuntos = {a.id: a.titulo for a in db.scalars(select(m.AgAsunto).where(m.AgAsunto.cr_cliente_id == c.id))}
    msgs = db.scalars(select(m.CnMensaje).where(m.CnMensaje.cliente_id == c.id, m.CnMensaje.organizacion_id == u.organizacion_id)
                      .order_by(m.CnMensaje.creado_en, m.CnMensaje.id)).all()
    for x in msgs:
        if x.autor == "cliente" and not x.leido_en:
            x.leido_en = m.ahora()
    db.commit()
    return {"cliente": {"id": c.id, "nombre": c.nombre}, "asuntos": [{"id": k, "titulo": v} for k, v in asuntos.items()],
            "mensajes": [{"id": x.id, "autor": x.autor, "texto": x.texto, "motivo": MOTIVOS.get(x.motivo or ""), "estado": x.estado,
                          "asunto": asuntos.get(x.asunto_id), "fecha": x.creado_en.isoformat(), "por": nombres.get(x.usuario_id),
                          "leido": bool(x.leido_en)} for x in msgs]}


class Respuesta(BaseModel):
    texto: str = Field(min_length=1, max_length=2000)
    asunto_id: int | None = None


@router.post("/mensajes/{cid}", status_code=201)
def responder(cid: int, d: Respuesta, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = obtener(db, m.CrCliente, cid, u)
    if d.asunto_id:
        a = obtener(db, m.AgAsunto, d.asunto_id, u)
        if a.cr_cliente_id != c.id:
            raise HTTPException(404, "No encontrado.")
    x = m.CnMensaje(organizacion_id=u.organizacion_id, cliente_id=c.id, asunto_id=d.asunto_id, autor="despacho", usuario_id=u.id,
                    texto=d.texto.strip(), estado="enviado")
    db.add(x)
    # responder atiende lo que el cliente había pedido
    for p in db.scalars(select(m.CnMensaje).where(m.CnMensaje.cliente_id == c.id, m.CnMensaje.autor == "cliente", m.CnMensaje.estado == "nuevo")):
        p.estado = "atendido"
    db.flush()
    auditar(db, u, "cn_mensaje_enviado", "cr_cliente", c.id, {"mensaje_id": x.id}, request)
    db.commit()
    return {"id": x.id}


@router.post("/mensajes/{cid}/atendido")
def atendido(cid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    c = obtener(db, m.CrCliente, cid, u)
    n = 0
    for p in db.scalars(select(m.CnMensaje).where(m.CnMensaje.cliente_id == c.id, m.CnMensaje.autor == "cliente", m.CnMensaje.estado == "nuevo")):
        p.estado, n = "atendido", n + 1
    auditar(db, u, "cn_mensajes_atendidos", "cr_cliente", c.id, {"n": n}, request)
    db.commit()
    return {"ok": True}
