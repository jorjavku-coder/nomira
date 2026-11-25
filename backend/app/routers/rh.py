"""Recursos humanos (módulo «rh»): empresas, empleados, incidencias, avisos con acuse, documentos y nómina de control."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, condecimal
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import auditar, puede_editar, solo_admin, usuario_actual
from ..services.rh import base as rb

router = APIRouter(prefix="/api/rh", tags=["Recursos humanos"])


def _emp(db: Session, eid: int, u: m.Usuario) -> m.RhEmpresa:
    x = db.get(m.RhEmpresa, eid)
    if not x or x.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "Empresa no encontrada.")
    return x


def _empleado(db: Session, eid: int, u: m.Usuario) -> m.RhEmpleado:
    x = db.get(m.RhEmpleado, eid)
    if not x or x.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "Empleado no encontrado.")
    return x


def empresa_dict(x: m.RhEmpresa, n: int = 0) -> dict:
    return {"id": x.id, "nombre": x.nombre, "propia": x.propia, "cliente_id": x.cliente_id, "rfc": x.rfc, "registro_patronal": x.registro_patronal,
            "periodicidad": x.periodicidad, "activa": x.activa, "empleados": n}


def empleado_dict(x: m.RhEmpleado, emp: m.RhEmpresa | None = None) -> dict:
    return {"id": x.id, "empresa_id": x.empresa_id, "empresa": emp.nombre if emp else None, "nombre": x.nombre, "puesto": x.puesto, "area": x.area,
            "email": x.email, "telefono": x.telefono, "rfc": x.rfc, "curp": x.curp, "nss": x.nss, "fecha_ingreso": x.fecha_ingreso.isoformat(),
            "tipo_contrato": x.tipo_contrato, "salario_diario": str(x.salario_diario), "estado": x.estado,
            "fecha_baja": x.fecha_baja.isoformat() if x.fecha_baja else None, "motivo_baja": x.motivo_baja, "notas": x.notas,
            "portal": bool(x.portal_token_hash), "portal_ultimo_acceso": x.portal_ultimo_acceso.isoformat() if x.portal_ultimo_acceso else None}


def incidencia_dict(i: m.RhIncidencia, e: m.RhEmpleado | None = None) -> dict:
    return {"id": i.id, "empleado_id": i.empleado_id, "empleado": e.nombre if e else None, "tipo": i.tipo, "tipo_texto": rb.TIPOS.get(i.tipo, i.tipo),
            "desde": i.desde.isoformat(), "hasta": i.hasta.isoformat(), "dias": float(i.dias), "motivo": i.motivo, "estado": i.estado, "origen": i.origen,
            "comentario": i.comentario, "archivo": bool(i.archivo), "creado_en": i.creado_en.isoformat()}


@router.get("/resumen")
def resumen(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    rb.empresa_propia(db, db.get(m.Organizacion, u.organizacion_id))
    db.commit()
    oid = u.organizacion_id
    n = dict(db.execute(select(m.RhEmpleado.empresa_id, func.count()).where(m.RhEmpleado.organizacion_id == oid, m.RhEmpleado.estado == "activo")
                        .group_by(m.RhEmpleado.empresa_id)).all())
    empresas = db.scalars(select(m.RhEmpresa).where(m.RhEmpresa.organizacion_id == oid).order_by(m.RhEmpresa.propia.desc(), m.RhEmpresa.nombre)).all()
    return {"empresas": [empresa_dict(x, n.get(x.id, 0)) for x in empresas],
            "activos": sum(n.values()),
            "solicitudes": db.scalar(select(func.count()).select_from(m.RhIncidencia).where(m.RhIncidencia.organizacion_id == oid, m.RhIncidencia.estado == "pendiente")) or 0,
            "documentos_por_revisar": db.scalar(select(func.count()).select_from(m.RhDocumento).where(m.RhDocumento.organizacion_id == oid,
                                                                                                       m.RhDocumento.estado == "por_revisar")) or 0,
            "tipos": rb.TIPOS, "documentos": rb.DOCUMENTOS, "requeridos": rb.REQUERIDOS, "periodicidades": {k: v[0] for k, v in rb.PERIODICIDAD.items()},
            "contratos": rb.CONTRATOS, "puede_editar": u.rol in ("administrador", "analista"), "es_admin": u.rol == "administrador"}


# ------------------------------------------------------------------ empresas

class EmpresaIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=200)
    cliente_id: int | None = None
    rfc: str | None = Field(None, max_length=13)
    registro_patronal: str | None = Field(None, max_length=20)
    periodicidad: str = "quincenal"
    activa: bool = True


def _aplicar_empresa(db: Session, x: m.RhEmpresa, d: EmpresaIn, u: m.Usuario) -> None:
    if d.periodicidad not in rb.PERIODICIDAD:
        raise HTTPException(422, "Periodicidad no válida.")
    if d.cliente_id:
        c = db.get(m.CrCliente, d.cliente_id)
        if not c or c.organizacion_id != u.organizacion_id:
            raise HTTPException(422, "Ese cliente no es de su despacho.")
    x.nombre, x.cliente_id, x.periodicidad, x.activa = d.nombre.strip(), d.cliente_id, d.periodicidad, d.activa
    x.rfc = (d.rfc or "").strip().upper() or None
    x.registro_patronal = (d.registro_patronal or "").strip().upper() or None


@router.post("/empresas", status_code=201)
def crear_empresa(d: EmpresaIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    x = m.RhEmpresa(organizacion_id=u.organizacion_id, nombre="")
    _aplicar_empresa(db, x, d, u)
    db.add(x)
    db.flush()
    auditar(db, u, "rh_empresa", "rh_empresa", x.id, {"accion": "crear"}, request)
    db.commit()
    return empresa_dict(x)


@router.put("/empresas/{eid}")
def editar_empresa(eid: int, d: EmpresaIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    x = _emp(db, eid, u)
    _aplicar_empresa(db, x, d, u)
    auditar(db, u, "rh_empresa", "rh_empresa", x.id, {"accion": "editar"}, request)
    db.commit()
    return empresa_dict(x)


# ------------------------------------------------------------------ empleados

class EmpleadoIn(BaseModel):
    empresa_id: int
    nombre: str = Field(min_length=3, max_length=200)
    puesto: str | None = Field(None, max_length=120)
    area: str | None = Field(None, max_length=120)
    email: str | None = Field(None, max_length=254)
    telefono: str | None = Field(None, max_length=30)
    rfc: str | None = Field(None, max_length=13)
    curp: str | None = Field(None, max_length=18)
    nss: str | None = Field(None, max_length=11)
    fecha_ingreso: date
    tipo_contrato: str = "indeterminado"
    salario_diario: condecimal(ge=0, max_digits=12, decimal_places=2)
    notas: str | None = Field(None, max_length=4000)


def _aplicar_empleado(db: Session, x: m.RhEmpleado, d: EmpleadoIn, u: m.Usuario) -> None:
    _emp(db, d.empresa_id, u)
    if d.tipo_contrato not in rb.CONTRATOS:
        raise HTTPException(422, "Tipo de contrato no válido.")
    if d.fecha_ingreso > date.today():
        pass  # se permite capturar ingresos futuros (contratación ya firmada)
    for campo, rx, msg in (("rfc", r"[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}", "RFC no válido."), ("curp", r"[A-Z]{4}\d{6}[HMX][A-Z]{5}[A-Z0-9]\d", "CURP no válida."),
                           ("nss", r"\d{11}", "El NSS son 11 dígitos.")):
        v = (getattr(d, campo) or "").strip().upper()
        if v and not __import__("re").fullmatch(rx, v):
            raise HTTPException(422, msg)
        setattr(x, campo, v or None)
    x.empresa_id, x.nombre, x.puesto, x.area = d.empresa_id, d.nombre.strip(), (d.puesto or "").strip() or None, (d.area or "").strip() or None
    x.email, x.telefono = (d.email or "").strip().lower() or None, (d.telefono or "").strip() or None
    x.fecha_ingreso, x.tipo_contrato, x.salario_diario, x.notas = d.fecha_ingreso, d.tipo_contrato, d.salario_diario, (d.notas or "").strip() or None


@router.get("/empleados")
def empleados(empresa: int | None = None, estado: str = "activo", u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    q = select(m.RhEmpleado).where(m.RhEmpleado.organizacion_id == u.organizacion_id)
    if empresa:
        q = q.where(m.RhEmpleado.empresa_id == empresa)
    if estado in ("activo", "baja"):
        q = q.where(m.RhEmpleado.estado == estado)
    filas = db.scalars(q.order_by(m.RhEmpleado.nombre)).all()
    emps = {x.id: x for x in db.scalars(select(m.RhEmpresa).where(m.RhEmpresa.organizacion_id == u.organizacion_id))}
    docs = dict(db.execute(select(m.RhDocumento.empleado_id, func.count(func.distinct(m.RhDocumento.tipo)))
                           .where(m.RhDocumento.organizacion_id == u.organizacion_id, m.RhDocumento.tipo.in_(rb.REQUERIDOS),
                                  m.RhDocumento.estado == "aceptado").group_by(m.RhDocumento.empleado_id)).all())
    hoy = date.today()
    return {"empleados": [{**empleado_dict(x, emps.get(x.empresa_id)), "documentos_completos": docs.get(x.id, 0), "documentos_requeridos": len(rb.REQUERIDOS),
                           "antiguedad": rb.anios_cumplidos(x.fecha_ingreso, hoy)} for x in filas]}


@router.post("/empleados", status_code=201)
def crear_empleado(d: EmpleadoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    x = m.RhEmpleado(organizacion_id=u.organizacion_id, empresa_id=d.empresa_id, nombre="", fecha_ingreso=d.fecha_ingreso, salario_diario=Decimal(0))
    _aplicar_empleado(db, x, d, u)
    db.add(x)
    db.flush()
    auditar(db, u, "rh_empleado", "rh_empleado", x.id, {"accion": "alta"}, request)  # sin datos personales
    db.commit()
    return empleado_dict(x)


@router.get("/empleados/{eid}")
def ficha(eid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    x = _empleado(db, eid, u)
    inc = db.scalars(select(m.RhIncidencia).where(m.RhIncidencia.empleado_id == x.id).order_by(m.RhIncidencia.desde.desc()).limit(100)).all()
    docs = db.scalars(select(m.RhDocumento).where(m.RhDocumento.empleado_id == x.id).order_by(m.RhDocumento.creado_en.desc())).all()
    recibos = db.execute(select(m.RhRecibo, m.RhPeriodo).join(m.RhPeriodo, m.RhPeriodo.id == m.RhRecibo.periodo_id)
                         .where(m.RhRecibo.empleado_id == x.id).order_by(m.RhPeriodo.inicio.desc()).limit(48)).all()
    tiene = {dd.tipo for dd in docs if dd.estado == "aceptado"}
    return {**empleado_dict(x, db.get(m.RhEmpresa, x.empresa_id)), "vacaciones": rb.vacaciones(db, x),
            "incidencias": [incidencia_dict(i) for i in inc],
            "documentos": [documento_dict(dd) for dd in docs], "faltantes": [k for k in rb.REQUERIDOS if k not in tiene],
            "recibos": [{"id": r.id, "periodo_id": p.id, "inicio": p.inicio.isoformat(), "fin": p.fin.isoformat(), "neto": str(r.neto), "estado": p.estado,
                         "visto": bool(r.visto_en)} for r, p in recibos]}


@router.put("/empleados/{eid}")
def editar_empleado(eid: int, d: EmpleadoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    x = _empleado(db, eid, u)
    _aplicar_empleado(db, x, d, u)
    auditar(db, u, "rh_empleado", "rh_empleado", x.id, {"accion": "editar"}, request)
    db.commit()
    return empleado_dict(x)


class BajaIn(BaseModel):
    fecha: date
    motivo: str = Field(min_length=3, max_length=200)


@router.post("/empleados/{eid}/baja")
def baja(eid: int, d: BajaIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    x = _empleado(db, eid, u)
    x.estado, x.fecha_baja, x.motivo_baja = "baja", d.fecha, d.motivo.strip()
    x.portal_token_hash, x.portal_nip_hash = None, None  # ya no entra al portal
    x.portal_version += 1
    auditar(db, u, "rh_empleado", "rh_empleado", x.id, {"accion": "baja"}, request)
    db.commit()
    return empleado_dict(x)


@router.post("/empleados/{eid}/reingreso")
def reingreso(eid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    x = _empleado(db, eid, u)
    x.estado, x.fecha_baja, x.motivo_baja = "activo", None, None
    auditar(db, u, "rh_empleado", "rh_empleado", x.id, {"accion": "reingreso"}, request)
    db.commit()
    return empleado_dict(x)


@router.post("/empleados/{eid}/portal")
def acceso_portal(eid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """Genera (o regenera) el enlace y el NIP del portal. Se muestran una sola vez."""
    x = _empleado(db, eid, u)
    if x.estado != "activo":
        raise HTTPException(409, "El empleado está dado de baja.")
    token, nip = rb.nuevo_acceso(x)
    auditar(db, u, "rh_portal_acceso", "rh_empleado", x.id, None, request)
    db.commit()
    return {"url": rb.enlace_portal(token), "nip": nip}


@router.delete("/empleados/{eid}/portal")
def quitar_portal(eid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    x = _empleado(db, eid, u)
    x.portal_token_hash, x.portal_nip_hash = None, None
    x.portal_version += 1
    auditar(db, u, "rh_portal_quitado", "rh_empleado", x.id, None, request)
    db.commit()
    return {"ok": True}


@router.delete("/empleados/{eid}")
def borrar_empleado(eid: int, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    """Borra el expediente completo (derechos ARCO o error de captura): datos, documentos, incidencias y recibos."""
    x = _empleado(db, eid, u)
    for dd in db.scalars(select(m.RhDocumento).where(m.RhDocumento.empleado_id == x.id)):
        rb.ruta(dd.archivo).unlink(missing_ok=True)
    for i in db.scalars(select(m.RhIncidencia).where(m.RhIncidencia.empleado_id == x.id, m.RhIncidencia.archivo.is_not(None))):
        rb.ruta(i.archivo).unlink(missing_ok=True)
    db.delete(x)
    auditar(db, u, "rh_empleado_borrado", "rh_empleado", eid, None, request)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ incidencias

class IncidenciaIn(BaseModel):
    tipo: str
    desde: date
    hasta: date
    dias: condecimal(ge=0, max_digits=5, decimal_places=1) | None = None
    motivo: str | None = Field(None, max_length=500)


def validar_incidencia(tipo: str, desde: date, hasta: date, dias) -> Decimal:
    if tipo not in rb.TIPOS:
        raise HTTPException(422, "Tipo no válido.")
    if hasta < desde:
        raise HTTPException(422, "La fecha final no puede ser anterior a la inicial.")
    if (hasta - desde).days > 366:
        raise HTTPException(422, "El periodo es demasiado largo.")
    return Decimal(str(dias)) if dias is not None else Decimal(rb.dias_laborables(desde, hasta) if tipo in ("vacaciones", "permiso", "permiso_sin_goce")
                                                               else (hasta - desde).days + 1)


@router.get("/incidencias")
def incidencias(estado: str | None = "pendiente", u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    q = select(m.RhIncidencia).where(m.RhIncidencia.organizacion_id == u.organizacion_id)
    if estado:
        q = q.where(m.RhIncidencia.estado == estado)
    filas = db.scalars(q.order_by(m.RhIncidencia.creado_en.desc()).limit(300)).all()
    emps = {e.id: e for e in db.scalars(select(m.RhEmpleado).where(m.RhEmpleado.id.in_({i.empleado_id for i in filas})))} if filas else {}
    return {"incidencias": [incidencia_dict(i, emps.get(i.empleado_id)) for i in filas]}


@router.post("/empleados/{eid}/incidencias", status_code=201)
def registrar_incidencia(eid: int, d: IncidenciaIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    """RH registra la incidencia ya aprobada (falta, retardo, incapacidad, vacaciones autorizadas…)."""
    x = _empleado(db, eid, u)
    dias = validar_incidencia(d.tipo, d.desde, d.hasta, d.dias)
    i = m.RhIncidencia(organizacion_id=x.organizacion_id, empleado_id=x.id, tipo=d.tipo, desde=d.desde, hasta=d.hasta, dias=dias,
                       motivo=(d.motivo or "").strip() or None, estado="aprobada", origen="rh", resuelta_por_id=u.id, resuelta_en=datetime.now(timezone.utc))
    db.add(i)
    db.flush()
    auditar(db, u, "rh_incidencia", "rh_empleado", x.id, {"tipo": d.tipo, "dias": str(dias)}, request)
    db.commit()
    return incidencia_dict(i)


class ResolverIn(BaseModel):
    aprobar: bool
    comentario: str | None = Field(None, max_length=500)


@router.post("/incidencias/{iid}/resolver")
def resolver(iid: int, d: ResolverIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    i = db.get(m.RhIncidencia, iid)
    if not i or i.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "Solicitud no encontrada.")
    if i.estado != "pendiente":
        raise HTTPException(409, "Esa solicitud ya se resolvió.")
    if not d.aprobar and not (d.comentario or "").strip():
        raise HTTPException(422, "Explique al empleado por qué se rechaza.")
    i.estado, i.comentario = ("aprobada" if d.aprobar else "rechazada"), (d.comentario or "").strip() or None
    i.resuelta_por_id, i.resuelta_en = u.id, datetime.now(timezone.utc)
    auditar(db, u, "rh_incidencia_resuelta", "rh_empleado", i.empleado_id, {"estado": i.estado}, request)
    db.commit()
    return incidencia_dict(i)


@router.delete("/incidencias/{iid}")
def cancelar_incidencia(iid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    i = db.get(m.RhIncidencia, iid)
    if not i or i.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "No encontrada.")
    i.estado = "cancelada"
    auditar(db, u, "rh_incidencia_cancelada", "rh_empleado", i.empleado_id, None, request)
    db.commit()
    return incidencia_dict(i)


@router.get("/incidencias/{iid}/archivo")
def archivo_incidencia(iid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    i = db.get(m.RhIncidencia, iid)
    if not i or i.organizacion_id != u.organizacion_id or not i.archivo:
        raise HTTPException(404, "No hay archivo.")
    p = rb.ruta(i.archivo)
    return FileResponse(p, media_type=rb.MIME.get(p.suffix, "application/octet-stream"), filename=i.archivo_nombre or p.name)


# ------------------------------------------------------------------ avisos

class AvisoIn(BaseModel):
    titulo: str = Field(min_length=3, max_length=200)
    cuerpo: str = Field(min_length=3, max_length=8000)
    empresa_id: int | None = None
    fijado: bool = False
    requiere_acuse: bool = False
    vigente_hasta: date | None = None


def _aviso_dict(db: Session, a: m.RhAviso) -> dict:
    q = select(m.RhEmpleado.id).where(m.RhEmpleado.organizacion_id == a.organizacion_id, m.RhEmpleado.estado == "activo")
    if a.empresa_id:
        q = q.where(m.RhEmpleado.empresa_id == a.empresa_id)
    destinatarios = set(db.scalars(q))
    leidos = set(db.scalars(select(m.RhAcuse.empleado_id).where(m.RhAcuse.aviso_id == a.id)))
    return {"id": a.id, "titulo": a.titulo, "cuerpo": a.cuerpo, "empresa_id": a.empresa_id, "fijado": a.fijado, "requiere_acuse": a.requiere_acuse,
            "vigente_hasta": a.vigente_hasta.isoformat() if a.vigente_hasta else None, "creado_en": a.creado_en.isoformat(),
            "destinatarios": len(destinatarios), "leidos": len(destinatarios & leidos)}


@router.get("/avisos")
def avisos(u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    filas = db.scalars(select(m.RhAviso).where(m.RhAviso.organizacion_id == u.organizacion_id).order_by(m.RhAviso.fijado.desc(), m.RhAviso.creado_en.desc())
                       .limit(200)).all()
    return {"avisos": [_aviso_dict(db, a) for a in filas]}


def _aplicar_aviso(db: Session, a: m.RhAviso, d: AvisoIn, u: m.Usuario) -> None:
    if d.empresa_id:
        _emp(db, d.empresa_id, u)
    a.titulo, a.cuerpo, a.empresa_id, a.fijado = d.titulo.strip(), d.cuerpo.strip(), d.empresa_id, d.fijado
    a.requiere_acuse, a.vigente_hasta = d.requiere_acuse, d.vigente_hasta


@router.post("/avisos", status_code=201)
def crear_aviso(d: AvisoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = m.RhAviso(organizacion_id=u.organizacion_id, titulo="", cuerpo="", creado_por_id=u.id)
    _aplicar_aviso(db, a, d, u)
    db.add(a)
    db.flush()
    auditar(db, u, "rh_aviso", "rh_aviso", a.id, {"accion": "publicar"}, request)
    db.commit()
    return _aviso_dict(db, a)


def _aviso(db: Session, aid: int, u: m.Usuario) -> m.RhAviso:
    a = db.get(m.RhAviso, aid)
    if not a or a.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "Aviso no encontrado.")
    return a


@router.put("/avisos/{aid}")
def editar_aviso(aid: int, d: AvisoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = _aviso(db, aid, u)
    _aplicar_aviso(db, a, d, u)
    auditar(db, u, "rh_aviso", "rh_aviso", a.id, {"accion": "editar"}, request)
    db.commit()
    return _aviso_dict(db, a)


@router.delete("/avisos/{aid}")
def borrar_aviso(aid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    a = _aviso(db, aid, u)
    db.delete(a)
    auditar(db, u, "rh_aviso", "rh_aviso", aid, {"accion": "borrar"}, request)
    db.commit()
    return {"ok": True}


@router.get("/avisos/{aid}/acuses")
def acuses(aid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    a = _aviso(db, aid, u)
    q = select(m.RhEmpleado).where(m.RhEmpleado.organizacion_id == a.organizacion_id, m.RhEmpleado.estado == "activo")
    if a.empresa_id:
        q = q.where(m.RhEmpleado.empresa_id == a.empresa_id)
    leidos = dict(db.execute(select(m.RhAcuse.empleado_id, m.RhAcuse.leido_en).where(m.RhAcuse.aviso_id == a.id)).all())
    return {"personas": [{"id": e.id, "nombre": e.nombre, "portal": bool(e.portal_token_hash),
                          "leido_en": leidos[e.id].isoformat() if e.id in leidos else None} for e in db.scalars(q.order_by(m.RhEmpleado.nombre))]}


# ------------------------------------------------------------------ documentos

def documento_dict(dd: m.RhDocumento) -> dict:
    return {"id": dd.id, "tipo": dd.tipo, "tipo_texto": rb.DOCUMENTOS.get(dd.tipo, dd.tipo), "nombre": dd.nombre, "tamano": dd.tamano, "origen": dd.origen,
            "estado": dd.estado, "nota": dd.nota, "creado_en": dd.creado_en.isoformat()}


@router.post("/empleados/{eid}/documentos", status_code=201)
async def subir_documento(eid: int, request: Request, tipo: str = Form(...), archivo: UploadFile = File(...),
                          u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    x = _empleado(db, eid, u)
    if tipo not in rb.DOCUMENTOS:
        raise HTTPException(422, "Tipo de documento no válido.")
    contenido = await archivo.read(rb.MAX_ARCHIVO + 1)
    try:
        rel, nombre = rb.guardar_archivo(x.organizacion_id, x.id, archivo.filename or "", contenido)
    except ValueError as e:
        raise HTTPException(422, str(e))
    dd = m.RhDocumento(organizacion_id=x.organizacion_id, empleado_id=x.id, tipo=tipo, archivo=rel, nombre=nombre, tamano=len(contenido))
    db.add(dd)
    db.flush()
    auditar(db, u, "rh_documento", "rh_empleado", x.id, {"tipo": tipo}, request)
    db.commit()
    return documento_dict(dd)


def _doc(db: Session, did: int, u: m.Usuario) -> m.RhDocumento:
    dd = db.get(m.RhDocumento, did)
    if not dd or dd.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "Documento no encontrado.")
    return dd


@router.get("/documentos/{did}")
def ver_documento(did: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    dd = _doc(db, did, u)
    p = rb.ruta(dd.archivo)
    if not p.exists():
        raise HTTPException(404, "No se encontró el archivo.")
    return FileResponse(p, media_type=rb.MIME.get(p.suffix, "application/octet-stream"), filename=dd.nombre, content_disposition_type="inline")


class RevisarIn(BaseModel):
    aceptar: bool
    nota: str | None = Field(None, max_length=300)


@router.post("/documentos/{did}/revisar")
def revisar_documento(did: int, d: RevisarIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    dd = _doc(db, did, u)
    if not d.aceptar and not (d.nota or "").strip():
        raise HTTPException(422, "Diga al empleado qué corregir.")
    dd.estado, dd.nota = ("aceptado" if d.aceptar else "rechazado"), (d.nota or "").strip() or None
    auditar(db, u, "rh_documento_revisado", "rh_empleado", dd.empleado_id, {"estado": dd.estado}, request)
    db.commit()
    return documento_dict(dd)


@router.delete("/documentos/{did}")
def borrar_documento(did: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    dd = _doc(db, did, u)
    rb.ruta(dd.archivo).unlink(missing_ok=True)
    db.delete(dd)
    auditar(db, u, "rh_documento_borrado", "rh_empleado", dd.empleado_id, None, request)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ nómina de control

class PeriodoIn(BaseModel):
    empresa_id: int
    inicio: date
    fin: date
    fecha_pago: date


def _periodo(db: Session, pid: int, u: m.Usuario) -> m.RhPeriodo:
    p = db.get(m.RhPeriodo, pid)
    if not p or p.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "Periodo no encontrado.")
    return p


def _periodo_dict(db: Session, p: m.RhPeriodo, con_recibos: bool = False) -> dict:
    recibos = db.scalars(select(m.RhRecibo).where(m.RhRecibo.periodo_id == p.id)).all()
    x = {"id": p.id, "empresa_id": p.empresa_id, "empresa": db.get(m.RhEmpresa, p.empresa_id).nombre, "inicio": p.inicio.isoformat(), "fin": p.fin.isoformat(),
         "fecha_pago": p.fecha_pago.isoformat(), "estado": p.estado, "empleados": len(recibos), "total": str(sum((r.neto for r in recibos), Decimal(0)))}
    if con_recibos:
        emps = {e.id: e for e in db.scalars(select(m.RhEmpleado).where(m.RhEmpleado.id.in_([r.empleado_id for r in recibos])))} if recibos else {}
        x["recibos"] = sorted([{"id": r.id, "empleado_id": r.empleado_id, "empleado": emps[r.empleado_id].nombre, "puesto": emps[r.empleado_id].puesto,
                                "salario_diario": str(emps[r.empleado_id].salario_diario), "dias_pagados": float(r.dias_pagados), "faltas": float(r.faltas),
                                "percepciones": r.percepciones, "deducciones": r.deducciones, "neto": str(r.neto), "visto": bool(r.visto_en)}
                               for r in recibos], key=lambda r: r["empleado"])
    return x


@router.get("/periodos")
def periodos(empresa: int | None = None, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    q = select(m.RhPeriodo).where(m.RhPeriodo.organizacion_id == u.organizacion_id)
    if empresa:
        q = q.where(m.RhPeriodo.empresa_id == empresa)
    return {"periodos": [_periodo_dict(db, p) for p in db.scalars(q.order_by(m.RhPeriodo.inicio.desc()).limit(100))]}


@router.post("/periodos", status_code=201)
def crear_periodo(d: PeriodoIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    emp = _emp(db, d.empresa_id, u)
    if d.fin < d.inicio or (d.fin - d.inicio).days > 31:
        raise HTTPException(422, "Revise las fechas del periodo (máximo un mes).")
    if db.scalar(select(m.RhPeriodo.id).where(m.RhPeriodo.empresa_id == emp.id, m.RhPeriodo.inicio <= d.fin, m.RhPeriodo.fin >= d.inicio)):
        raise HTTPException(409, "Ya hay un periodo de nómina que se cruza con esas fechas.")
    p = m.RhPeriodo(organizacion_id=u.organizacion_id, empresa_id=emp.id, inicio=d.inicio, fin=d.fin, fecha_pago=d.fecha_pago)
    db.add(p)
    db.flush()
    activos = db.scalars(select(m.RhEmpleado).where(m.RhEmpleado.empresa_id == emp.id, m.RhEmpleado.fecha_ingreso <= d.fin,
                                                    (m.RhEmpleado.estado == "activo") | (m.RhEmpleado.fecha_baja >= d.inicio))).all()
    if not activos:
        raise HTTPException(422, "Esa empresa no tiene empleados activos en esas fechas.")
    for e in activos:
        r = rb.armar_recibo(db, p, e)
        db.add(m.RhRecibo(organizacion_id=u.organizacion_id, periodo_id=p.id, empleado_id=e.id, dias_pagados=r["dias_pagados"], faltas=r["faltas"],
                          percepciones=r["percepciones"], deducciones=r["deducciones"], neto=rb.neto(r["percepciones"], r["deducciones"])))
    auditar(db, u, "rh_periodo", "rh_periodo", p.id, {"accion": "crear", "empleados": len(activos)}, request)
    db.commit()
    return _periodo_dict(db, p, True)


@router.get("/periodos/{pid}")
def ver_periodo(pid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return _periodo_dict(db, _periodo(db, pid, u), True)


class Concepto(BaseModel):
    concepto: str = Field(min_length=1, max_length=80)
    importe: condecimal(ge=0, max_digits=12, decimal_places=2)


class ReciboIn(BaseModel):
    percepciones: list[Concepto] = Field(max_length=30)
    deducciones: list[Concepto] = Field(max_length=30)


@router.put("/recibos/{rid}")
def editar_recibo(rid: int, d: ReciboIn, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    r = db.get(m.RhRecibo, rid)
    if not r or r.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "Recibo no encontrado.")
    if db.get(m.RhPeriodo, r.periodo_id).estado != "borrador":
        raise HTTPException(409, "El periodo está cerrado. Reábralo para corregir.")
    r.percepciones = [{"concepto": c.concepto.strip(), "importe": str(c.importe)} for c in d.percepciones]
    r.deducciones = [{"concepto": c.concepto.strip(), "importe": str(c.importe)} for c in d.deducciones]
    r.neto = rb.neto(r.percepciones, r.deducciones)
    if r.neto < 0:
        raise HTTPException(422, "Las deducciones no pueden ser mayores que las percepciones.")
    auditar(db, u, "rh_recibo", "rh_periodo", r.periodo_id, {"recibo": r.id}, request)  # sin importes
    db.commit()
    return {"id": r.id, "neto": str(r.neto), "percepciones": r.percepciones, "deducciones": r.deducciones}


@router.post("/periodos/{pid}/cerrar")
def cerrar(pid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    p = _periodo(db, pid, u)
    p.estado, p.cerrado_en = "cerrado", datetime.now(timezone.utc)
    auditar(db, u, "rh_periodo", "rh_periodo", p.id, {"accion": "cerrar"}, request)
    db.commit()
    return _periodo_dict(db, p)


@router.post("/periodos/{pid}/reabrir")
def reabrir(pid: int, request: Request, u: m.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    p = _periodo(db, pid, u)
    p.estado, p.cerrado_en = "borrador", None
    auditar(db, u, "rh_periodo", "rh_periodo", p.id, {"accion": "reabrir"}, request)
    db.commit()
    return _periodo_dict(db, p)


@router.delete("/periodos/{pid}")
def borrar_periodo(pid: int, request: Request, u: m.Usuario = Depends(puede_editar), db: Session = Depends(get_db)):
    p = _periodo(db, pid, u)
    if p.estado != "borrador":
        raise HTTPException(409, "Solo se puede borrar un periodo en borrador.")
    db.delete(p)
    auditar(db, u, "rh_periodo", "rh_periodo", pid, {"accion": "borrar"}, request)
    db.commit()
    return {"ok": True}


@router.get("/periodos/{pid}/excel")
def excel(pid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    p = _periodo(db, pid, u)
    return Response(rb.excel_periodo(db, p), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="nomina-{p.inicio:%Y%m%d}-{p.fin:%Y%m%d}.xlsx"'})


@router.get("/recibos/{rid}/pdf")
def recibo_pdf(rid: int, u: m.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    r = db.get(m.RhRecibo, rid)
    if not r or r.organizacion_id != u.organizacion_id:
        raise HTTPException(404, "Recibo no encontrado.")
    p = db.get(m.RhPeriodo, r.periodo_id)
    e = db.get(m.RhEmpleado, r.empleado_id)
    return Response(rb.recibo_pdf(r, e, db.get(m.RhEmpresa, p.empresa_id), p), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="recibo-{p.fin:%Y%m%d}-{e.id}.pdf"'})
