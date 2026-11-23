"""Nomira Escrituración (panel de la notaría): expedientes por acto, partes (desde Clientes), avance por etapas,
requisitos con vigencia y semáforo «listo para firmar», y enlaces de seguimiento para clientes, inmobiliarias y bancos.

Leer: cualquier rol. Capturar: administrador y analista. Todo se filtra por organización."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, condecimal
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, puede_editar, usuario_actual
from ..services import almacenamiento as almacen
from ..services.agenda.base import hoy
from ..services.clientes import base as clientes_base
from ..services.escrituracion import base as eb
from ..services.evidencia import solicitudes as sol

router = APIRouter(prefix="/api/escrituracion", tags=["Nomira Escrituración"])
Monto = condecimal(ge=0, max_digits=14, decimal_places=2)


def _txt(v: str | None, n: int) -> str | None:
    v = re.sub(r"\s+", " ", v or "").strip()
    return v[:n] or None


def _exp(db: Session, eid: int, u: m.Usuario) -> m.EsExpediente:
    e = db.get(m.EsExpediente, eid)
    if not e or e.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrado.")
    return e


def _de_exp(db: Session, modelo, oid: int, u: m.Usuario):
    x = db.get(modelo, oid)
    e = db.get(m.EsExpediente, x.expediente_id) if x else None
    if not x or not e or e.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrado.")
    return x, e


def _nombres(db: Session, org: int) -> dict[int, str]:
    return dict(db.execute(select(m.Usuario.id, m.Usuario.nombre).where(m.Usuario.organizacion_id == org)).all())


@router.get("/catalogos")
def catalogos(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    us = db.scalars(select(m.Usuario).where(m.Usuario.organizacion_id == u.organizacion_id, m.Usuario.activo.is_(True), m.Usuario.eliminado_en.is_(None))
                    .order_by(m.Usuario.nombre))
    return {"actos": eb.ACTOS, "roles": eb.ROLES, "roles_por_acto": eb.ROLES_POR_ACTO, "usuarios": [{"id": x.id, "nombre": x.nombre} for x in us],
            "puede_editar": u.rol in ("administrador", "analista"), "yo": u.id}


# ------------------------------------------------------------------ vistas

def _datos(db: Session, e: m.EsExpediente) -> tuple[list, list, dict]:
    hitos = list(db.scalars(select(m.EsHito).where(m.EsHito.expediente_id == e.id).order_by(m.EsHito.orden)))
    reqs = list(db.scalars(select(m.EsRequisito).where(m.EsRequisito.expediente_id == e.id).order_by(m.EsRequisito.parte_id.nullsfirst(), m.EsRequisito.id)))
    partes = {p.id: p for p in db.scalars(select(m.EsParte).where(m.EsParte.expediente_id == e.id).order_by(m.EsParte.id))}
    return hitos, reqs, partes


def _resumen(db: Session, e: m.EsExpediente, nombres: dict) -> dict:
    hitos, reqs, partes = _datos(db, e)
    return {"id": e.id, "folio": e.folio, "acto": e.acto, "acto_texto": eb.ACTOS.get(e.acto, e.acto), "titulo": e.titulo, "inmueble": e.inmueble,
            "estado": e.estado, "responsable_id": e.responsable_id, "responsable": nombres.get(e.responsable_id),
            "cita_firma": e.cita_firma.isoformat() if e.cita_firma else None, "cita_lugar": e.cita_lugar,
            "partes": [{"id": p.id, "rol": p.rol, "rol_texto": eb.ROLES.get(p.rol, p.rol), "nombre": p.nombre} for p in partes.values()],
            "avance": eb.avance(hitos), "semaforo": eb.semaforo(e, reqs, partes, hoy()),
            "del_cliente": sum(1 for r in reqs if r.estado == "recibido" and r.origen == "cliente"),
            "actualizado_en": e.actualizado_en.isoformat()}


@router.get("/expedientes")
def lista(estado: str = "abierto", q: str | None = None, responsable_id: int | None = None, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    s = select(m.EsExpediente).where(m.EsExpediente.organizacion_id == u.organizacion_id)
    if estado != "todos":
        s = s.where(m.EsExpediente.estado == estado)
    if responsable_id:
        s = s.where(m.EsExpediente.responsable_id == responsable_id)
    if q and q.strip():
        t = f"%{q.strip()[:80]}%"
        con_parte = select(m.EsParte.expediente_id).where(m.EsParte.nombre.ilike(t))
        s = s.where(or_(m.EsExpediente.titulo.ilike(t), m.EsExpediente.folio.ilike(t), m.EsExpediente.inmueble.ilike(t),
                        m.EsExpediente.numero_escritura.ilike(t), m.EsExpediente.id.in_(con_parte)))
    nombres = _nombres(db, u.organizacion_id)
    filas = [_resumen(db, e, nombres) for e in db.scalars(s.order_by(m.EsExpediente.cita_firma.asc().nullslast(), m.EsExpediente.id.desc()).limit(500))]
    return {"expedientes": filas, "puede_editar": u.rol in ("administrador", "analista"),
            "totales": {c: sum(1 for f in filas if f["semaforo"]["color"] == c) for c in ("rojo", "amarillo", "verde")}}


def _req_dict(r: m.EsRequisito, partes: dict, nombres: dict, ref: date) -> dict:
    return {"id": r.id, "parte_id": r.parte_id, "de": partes[r.parte_id].nombre if r.parte_id in partes else "Inmueble / operación",
            "clave": r.clave, "nombre": r.nombre, "obligatorio": r.obligatorio, "vigencia_dias": r.vigencia_dias, "estado": r.estado,
            "expedido_en": r.expedido_en.isoformat() if r.expedido_en else None, "vence_en": r.vence_en.isoformat() if r.vence_en else None,
            "vencido": bool(r.vence_en and r.vence_en < ref), "nota": r.nota, "tiene_archivo": bool(r.archivo), "archivo_nombre": r.archivo_nombre,
            "origen": r.origen, "recibido_en": r.recibido_en.isoformat() if r.recibido_en else None, "validado_por": nombres.get(r.validado_por_id)}


@router.get("/expedientes/{eid}")
def ver(eid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    e = _exp(db, eid, u)
    nombres = _nombres(db, u.organizacion_id)
    hitos, reqs, partes = _datos(db, e)
    sem = eb.semaforo(e, reqs, partes, hoy())
    ref = date.fromisoformat(sem["referencia"])
    accesos = db.scalars(select(m.EsAcceso).where(m.EsAcceso.expediente_id == e.id).order_by(m.EsAcceso.id.desc())).all()
    return {**_resumen(db, e, nombres), "folio_real": e.folio_real, "clave_catastral": e.clave_catastral,
            "valor_operacion": str(e.valor_operacion) if e.valor_operacion is not None else None, "numero_escritura": e.numero_escritura,
            "volumen": e.volumen, "folio_registro": e.folio_registro, "mensaje_cliente": e.mensaje_cliente, "notas": e.notas,
            "creado_en": e.creado_en.isoformat(),
            "partes": [{"id": p.id, "rol": p.rol, "rol_texto": eb.ROLES.get(p.rol, p.rol), "nombre": p.nombre, "tipo": p.tipo, "email": p.email,
                        "telefono": p.telefono, "casado": p.casado, "cr_cliente_id": p.cr_cliente_id} for p in partes.values()],
            "hitos": [{"id": h.id, "clave": h.clave, "nombre": h.nombre, "orden": h.orden, "estado": h.estado, "fecha": h.fecha.isoformat() if h.fecha else None,
                       "nota_publica": h.nota_publica, "visible_cliente": h.visible_cliente, "actualizado_por": nombres.get(h.actualizado_por_id)} for h in hitos],
            "requisitos": [_req_dict(r, partes, nombres, ref) for r in reqs],
            "accesos": [{"id": a.id, "tipo": a.tipo, "nombre": a.nombre, "email": a.email, "avisar": a.avisar, "parte_id": a.parte_id,
                         "estado": "revocado" if a.revocado_en else ("vencido" if sol._aware(a.expira_en) <= m.ahora() else "activo"),
                         "expira_en": a.expira_en.isoformat(), "ultimo_acceso": a.ultimo_acceso.isoformat() if a.ultimo_acceso else None,
                         "visitas": a.visitas, "pista": a.token_pista} for a in accesos]}


# ------------------------------------------------------------------ alta y datos

class ParteIn(BaseModel):
    rol: str
    cr_cliente_id: int | None = None
    nombre: str | None = Field(None, max_length=250)
    tipo: str = "fisica"
    email: str | None = Field(None, max_length=254)
    telefono: str | None = Field(None, max_length=30)
    casado: bool = False


class ExpedienteIn(BaseModel):
    acto: str
    titulo: str = Field(min_length=3, max_length=200)
    inmueble: str | None = Field(None, max_length=500)
    folio_real: str | None = Field(None, max_length=60)
    clave_catastral: str | None = Field(None, max_length=60)
    valor_operacion: Monto | None = None
    responsable_id: int | None = None
    cita_firma: datetime | None = None
    cita_lugar: str | None = Field(None, max_length=300)
    numero_escritura: str | None = Field(None, max_length=30)
    volumen: str | None = Field(None, max_length=30)
    folio_registro: str | None = Field(None, max_length=60)
    mensaje_cliente: str | None = Field(None, max_length=1000)
    notas: str | None = Field(None, max_length=10000)
    partes: list[ParteIn] = Field(default_factory=list, max_length=20)


def _parte(db: Session, e: m.EsExpediente, d: ParteIn, u: m.Usuario) -> m.EsParte:
    if d.rol not in eb.ROLES or d.tipo not in ("fisica", "moral"):
        raise HTTPException(422, "Revise el rol y el tipo de persona.")
    cli = clientes_base.de_org(db, d.cr_cliente_id, u.organizacion_id)
    nombre = cli.nombre if cli else _txt(d.nombre, 250)
    if not nombre:
        raise HTTPException(422, "Elija la persona en Clientes o escriba su nombre.")
    p = m.EsParte(expediente_id=e.id, rol=d.rol, cr_cliente_id=cli.id if cli else None, nombre=nombre, tipo=cli.tipo if cli else d.tipo,
                  email=(cli.email if cli else None) or _txt(d.email, 254), telefono=(cli.telefono if cli else None) or _txt(d.telefono, 20), casado=d.casado)
    db.add(p)
    db.flush()
    eb.agregar_requisitos(db, e.id, eb.requisitos_parte(p), p.id)
    if cli:  # lo que ya está en los documentos del cliente se marca como recibido (se valida en la notaría)
        docs = {x.tipo for x in db.scalars(select(m.CrDocumento).where(m.CrDocumento.cliente_id == cli.id))}
        db.flush()
        mapa = {"identificacion": "identificacion", "csf": "constancia", "domicilio": "domicilio", "poder_representante": "poder"}
        for r in db.scalars(select(m.EsRequisito).where(m.EsRequisito.parte_id == p.id)):
            if mapa.get(r.clave) in docs:
                r.estado, r.origen, r.recibido_en, r.nota = "recibido", "notaria", m.ahora(), "Está en los documentos del cliente (Clientes)."
    return p


def _aplicar(db: Session, e: m.EsExpediente, d: ExpedienteIn, u: m.Usuario) -> None:
    if d.responsable_id:
        r = db.get(m.Usuario, d.responsable_id)
        if not r or r.organizacion_id != u.organizacion_id:
            raise HTTPException(422, "Responsable no válido.")
    e.titulo, e.inmueble, e.folio_real, e.clave_catastral = _txt(d.titulo, 200), _txt(d.inmueble, 500), _txt(d.folio_real, 60), _txt(d.clave_catastral, 60)
    e.valor_operacion, e.responsable_id, e.cita_firma, e.cita_lugar = d.valor_operacion, d.responsable_id, d.cita_firma, _txt(d.cita_lugar, 300)
    e.numero_escritura, e.volumen, e.folio_registro = _txt(d.numero_escritura, 30), _txt(d.volumen, 30), _txt(d.folio_registro, 60)
    e.mensaje_cliente, e.notas = (d.mensaje_cliente or "").strip()[:1000] or None, (d.notas or "").strip() or None


@router.post("/expedientes", status_code=201)
def crear(d: ExpedienteIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    if d.acto not in eb.ACTOS:
        raise HTTPException(422, "Elija el acto.")
    e = m.EsExpediente(organizacion_id=u.organizacion_id, acto=d.acto, folio=eb.siguiente_folio(db, u.organizacion_id, hoy().year), creado_por_id=u.id)
    _aplicar(db, e, d, u)
    e.responsable_id = e.responsable_id or u.id
    db.add(e)
    db.flush()
    eb.crear_etapas(db, e)
    eb.agregar_requisitos(db, e.id, eb.plantilla_requisitos(e.acto))
    for p in d.partes:
        _parte(db, e, p, u)
    auditar(db, u, "es_expediente_creado", "es_expediente", e.id, {"acto": e.acto}, request)
    db.commit()
    return ver(e.id, u, db)


@router.put("/expedientes/{eid}")
def editar(eid: int, d: ExpedienteIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    e = _exp(db, eid, u)
    _aplicar(db, e, d, u)
    auditar(db, u, "es_expediente_editado", "es_expediente", e.id, None, request)
    db.commit()
    return ver(e.id, u, db)


class EstadoIn(BaseModel):
    estado: str


@router.post("/expedientes/{eid}/estado")
def estado(eid: int, d: EstadoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    e = _exp(db, eid, u)
    if d.estado not in ("abierto", "concluido", "cancelado"):
        raise HTTPException(422, "Estado no válido.")
    e.estado = d.estado
    auditar(db, u, "es_expediente_estado", "es_expediente", e.id, {"estado": d.estado}, request)
    db.commit()
    return ver(e.id, u, db)


@router.post("/expedientes/{eid}/partes", status_code=201)
def agregar_parte(eid: int, d: ParteIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    e = _exp(db, eid, u)
    _parte(db, e, d, u)
    auditar(db, u, "es_parte_agregada", "es_expediente", e.id, {"rol": d.rol}, request)
    db.commit()
    return ver(e.id, u, db)


@router.delete("/partes/{pid}")
def quitar_parte(pid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    p, e = _de_exp(db, m.EsParte, pid, u)
    for r in db.scalars(select(m.EsRequisito).where(m.EsRequisito.parte_id == p.id)):
        eb.borrar_archivo(r.archivo)
    db.delete(p)
    auditar(db, u, "es_parte_quitada", "es_expediente", e.id, None, request)
    db.commit()
    almacen.olvidar(u.organizacion_id)
    return ver(e.id, u, db)


# ------------------------------------------------------------------ avance (etapas)

class HitoIn(BaseModel):
    estado: str
    fecha: date | None = None
    nota_publica: str | None = Field(None, max_length=500)
    visible_cliente: bool = True


@router.put("/hitos/{hid}")
def hito(hid: int, d: HitoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    h, e = _de_exp(db, m.EsHito, hid, u)
    if d.estado not in ("pendiente", "en_proceso", "observado", "hecho", "no_aplica"):
        raise HTTPException(422, "Estado no válido.")
    if d.estado == "observado" and not (d.nota_publica or "").strip():
        raise HTTPException(422, "Explique la observación (por ejemplo, qué pidió el Registro y qué se está haciendo).")
    nuevo_hecho = d.estado == "hecho" and h.estado != "hecho"
    h.estado, h.nota_publica, h.visible_cliente = d.estado, (d.nota_publica or "").strip() or None, d.visible_cliente
    h.fecha = d.fecha or (hoy() if d.estado == "hecho" else None)
    h.actualizado_por_id, h.actualizado_en = u.id, m.ahora()
    if h.clave == "entregado" and d.estado == "hecho":
        e.estado = "concluido"
    e.actualizado_en = m.ahora()
    auditar(db, u, "es_etapa", "es_expediente", e.id, {"etapa": h.clave, "estado": d.estado}, request)
    db.commit()
    if nuevo_hecho and h.visible_cliente:
        eb.avisar_avance(db, e, h)
        db.commit()
    return ver(e.id, u, db)


# ------------------------------------------------------------------ requisitos

class RequisitoNuevo(BaseModel):
    nombre: str = Field(min_length=2, max_length=160)
    parte_id: int | None = None
    obligatorio: bool = True
    vigencia_dias: int | None = Field(None, ge=1, le=3650)


@router.post("/expedientes/{eid}/requisitos", status_code=201)
def nuevo_requisito(eid: int, d: RequisitoNuevo, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    e = _exp(db, eid, u)
    if d.parte_id:
        p = db.get(m.EsParte, d.parte_id)
        if not p or p.expediente_id != e.id:
            raise HTTPException(422, "Esa persona no es parte de este expediente.")
    db.add(m.EsRequisito(expediente_id=e.id, parte_id=d.parte_id, clave="otro", nombre=d.nombre.strip(), obligatorio=d.obligatorio, vigencia_dias=d.vigencia_dias))
    db.commit()
    return ver(e.id, u, db)


class RequisitoIn(BaseModel):
    estado: str
    expedido_en: date | None = None
    vence_en: date | None = None
    vigencia_dias: int | None = Field(None, ge=1, le=3650)
    obligatorio: bool = True
    nota: str | None = Field(None, max_length=500)


@router.put("/requisitos/{rid}")
def requisito(rid: int, d: RequisitoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    r, e = _de_exp(db, m.EsRequisito, rid, u)
    if d.estado not in ("pendiente", "recibido", "validado", "rechazado", "no_aplica"):
        raise HTTPException(422, "Estado no válido.")
    if d.estado == "rechazado" and not (d.nota or "").strip():
        raise HTTPException(422, "Diga qué hay que corregir: el cliente lo verá en su enlace.")
    if d.expedido_en and d.expedido_en > hoy():
        raise HTTPException(422, "La fecha de expedición no puede ser futura.")
    r.estado, r.obligatorio, r.vigencia_dias, r.nota = d.estado, d.obligatorio, d.vigencia_dias, (d.nota or "").strip() or None
    r.expedido_en, r.vence_en = d.expedido_en, d.vence_en
    if d.expedido_en and d.vigencia_dias and not d.vence_en:
        eb.calcular_vence(r)
    if d.estado in ("recibido", "validado") and not r.recibido_en:
        r.recibido_en, r.origen = m.ahora(), r.origen or "notaria"
    r.validado_por_id, r.validado_en = (u.id, m.ahora()) if d.estado == "validado" else (None, None)
    e.actualizado_en = m.ahora()
    auditar(db, u, "es_requisito", "es_expediente", e.id, {"requisito": r.clave, "estado": d.estado}, request)
    db.commit()
    return ver(e.id, u, db)


@router.delete("/requisitos/{rid}")
def borrar_requisito(rid: int, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    r, e = _de_exp(db, m.EsRequisito, rid, u)
    eb.borrar_archivo(r.archivo)
    db.delete(r)
    db.commit()
    almacen.olvidar(u.organizacion_id)
    return ver(e.id, u, db)


def guardar(db: Session, r: m.EsRequisito, e: m.EsExpediente, contenido: bytes, nombre: str | None, origen: str) -> None:
    if len(contenido) > eb.MAX_ARCHIVO:
        raise HTTPException(413, "El archivo pesa más de 15 MB.")
    gb = almacen.contratado_gb(db, e.organizacion_id)
    if gb and almacen.uso_bytes(e.organizacion_id, fresco=True) + len(contenido) > gb * almacen.GB:
        raise HTTPException(413, "La notaría ya no tiene espacio de almacenamiento disponible.")
    try:
        rel, mime = eb.guardar_archivo(e.organizacion_id, e.id, contenido)
    except ValueError:
        raise HTTPException(415, "Solo se aceptan archivos PDF, JPG, PNG o WebP.")
    eb.borrar_archivo(r.archivo)
    r.archivo, r.archivo_mime, r.archivo_nombre = rel, mime, (Path((nombre or "documento").replace("\\", "/")).name or "documento")[:200]
    r.estado, r.origen, r.recibido_en, r.validado_por_id, r.validado_en = "recibido", origen, m.ahora(), None, None
    if origen == "cliente":
        r.nota = None
    e.actualizado_en = m.ahora()
    almacen.olvidar(e.organizacion_id)


@router.post("/requisitos/{rid}/archivo")
async def subir(rid: int, request: Request, archivo: UploadFile = File(...), u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    r, e = _de_exp(db, m.EsRequisito, rid, u)
    contenido = await archivo.read(eb.MAX_ARCHIVO + 1)
    guardar(db, r, e, contenido, archivo.filename, "notaria")
    auditar(db, u, "es_documento", "es_expediente", e.id, {"requisito": r.clave}, request)
    db.commit()
    return ver(e.id, u, db)


@router.get("/requisitos/{rid}/archivo")
def descargar(rid: int, request: Request, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    r, e = _de_exp(db, m.EsRequisito, rid, u)
    ruta = Path(ajustes().storage_dir, r.archivo) if r.archivo else None
    if not ruta or not ruta.exists():
        raise HTTPException(404, "Sin archivo.")
    auditar(db, u, "es_documento_visto", "es_expediente", e.id, {"requisito": r.clave}, request)
    db.commit()
    return FileResponse(ruta, media_type=r.archivo_mime or "application/octet-stream", filename=r.archivo_nombre or ruta.name,
                        content_disposition_type="inline", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


# ------------------------------------------------------------------ enlaces de seguimiento

class AccesoIn(BaseModel):
    parte_id: int | None = None
    tipo: str = "parte"
    nombre: str | None = Field(None, max_length=200)
    email: str | None = Field(None, max_length=254)
    avisar: bool = True
    dias: int = Field(180, ge=7, le=730)


@router.post("/expedientes/{eid}/accesos", status_code=201)
def nuevo_acceso(eid: int, d: AccesoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    e = _exp(db, eid, u)
    if d.tipo not in ("parte", "inmobiliaria", "banco", "otro"):
        raise HTTPException(422, "Tipo no válido.")
    p = None
    if d.tipo == "parte":
        p = db.get(m.EsParte, d.parte_id) if d.parte_id else None
        if not p or p.expediente_id != e.id:
            raise HTTPException(422, "Elija la parte.")
    nombre = _txt(d.nombre, 200) or (p.nombre if p else None)
    if not nombre:
        raise HTTPException(422, "Escriba el nombre de la inmobiliaria, banco o persona.")
    email = (d.email or (p.email if p else None) or "").strip().lower() or None
    if email and not sol.email_valido(email):
        raise HTTPException(422, "Correo electrónico inválido.")
    token = sol.nuevo_token()
    a = m.EsAcceso(organizacion_id=e.organizacion_id, expediente_id=e.id, parte_id=p.id if p else None, tipo=d.tipo, nombre=nombre, email=email,
                   avisar=d.avisar and bool(email), token_hash=sol.huella(token), token_pista=token[:4],
                   expira_en=m.ahora() + timedelta(days=d.dias), creado_por_id=u.id)
    db.add(a)
    db.flush()
    auditar(db, u, "es_enlace_creado", "es_expediente", e.id, {"tipo": d.tipo}, request)
    db.commit()
    return {"id": a.id, "enlace": ajustes().url_publica.rstrip("/") + "/seguimiento#" + token,
            "aviso": "Copie el enlace ahora: por seguridad no se vuelve a mostrar."}


@router.post("/accesos/{aid}/revocar")
def revocar(aid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = db.get(m.EsAcceso, aid)
    if not a or a.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrado.")
    a.revocado_en = a.revocado_en or m.ahora()
    auditar(db, u, "es_enlace_revocado", "es_expediente", a.expediente_id, None, request)
    db.commit()
    return ver(a.expediente_id, u, db)

