"""Portal del empleado: avisos con acuse, vacaciones y solicitudes, recibos y documentos. Enlace personal + NIP."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import ip_cliente
from ..freno import Ventana
from ..security import gastar_tiempo_de_verificacion, verificar_contrasena
from ..services import modulos
from ..services.rh import base as rb
from .rh import documento_dict, incidencia_dict, validar_incidencia

router = APIRouter(prefix="/api/portal-rh", tags=["Portal del empleado"])
_intentos_ip = Ventana(20, 900)
_intentos_enlace = Ventana(6, 900)


def _por_enlace(db: Session, token: str, request: Request) -> m.RhEmpleado:
    ip = ip_cliente(request) or "?"
    if _intentos_ip.excedida(ip):
        raise HTTPException(429, "Demasiados intentos. Espere unos minutos.")
    e = db.scalar(select(m.RhEmpleado).where(m.RhEmpleado.portal_token_hash == rb.huella(token))) if len(token) < 100 else None
    if not e or e.estado != "activo" or not modulos.estado(db, e.organizacion_id)["rh"]["activo"]:
        _intentos_ip.registrar(ip)
        raise HTTPException(404, "Este enlace no es válido. Pida uno nuevo a Recursos Humanos.")
    return e


@router.get("/acceso/{token}")
def acceso(token: str, request: Request, db: Session = Depends(get_db)):
    e = _por_enlace(db, token, request)
    return {"nombre": e.nombre.split(" ")[0], "empresa": db.get(m.RhEmpresa, e.empresa_id).nombre}


class EntrarIn(BaseModel):
    nip: str


@router.post("/acceso/{token}/entrar")
def entrar(token: str, d: EntrarIn, request: Request, db: Session = Depends(get_db)):
    e = _por_enlace(db, token, request)
    clave = f"rh-{e.id}"
    if _intentos_enlace.excedida(clave):
        raise HTTPException(429, "Demasiados intentos con este enlace. Espere 15 minutos o pida un NIP nuevo a RH.")
    if not e.portal_nip_hash or not verificar_contrasena(d.nip.strip(), e.portal_nip_hash):
        if not e.portal_nip_hash:
            gastar_tiempo_de_verificacion(d.nip)
        _intentos_enlace.registrar(clave)
        raise HTTPException(401, "NIP incorrecto.")
    e.portal_ultimo_acceso = datetime.now(timezone.utc)
    db.commit()
    return {"sesion": rb.token_sesion(e)}


def empleado_portal(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> m.RhEmpleado:
    datos = rb.leer_sesion((authorization or "").removeprefix("Bearer ").strip())
    e = db.get(m.RhEmpleado, int(datos["sub"])) if datos else None
    if not e or e.portal_version != datos.get("ver") or e.estado != "activo" or not e.portal_token_hash:
        raise HTTPException(401, "Su sesión terminó. Vuelva a entrar con su enlace y su NIP.")
    return e


@router.get("/yo")
def yo(e: m.RhEmpleado = Depends(empleado_portal), db: Session = Depends(get_db)):
    emp = db.get(m.RhEmpresa, e.empresa_id)
    avisos = rb.avisos_vigentes(db, e.organizacion_id, e.empresa_id)
    leidos = set(db.scalars(select(m.RhAcuse.aviso_id).where(m.RhAcuse.empleado_id == e.id)))
    inc = db.scalars(select(m.RhIncidencia).where(m.RhIncidencia.empleado_id == e.id).order_by(m.RhIncidencia.desde.desc()).limit(40)).all()
    recibos = db.execute(select(m.RhRecibo, m.RhPeriodo).join(m.RhPeriodo, m.RhPeriodo.id == m.RhRecibo.periodo_id)
                         .where(m.RhRecibo.empleado_id == e.id, m.RhPeriodo.estado == "cerrado").order_by(m.RhPeriodo.inicio.desc()).limit(24)).all()
    docs = db.scalars(select(m.RhDocumento).where(m.RhDocumento.empleado_id == e.id).order_by(m.RhDocumento.creado_en.desc())).all()
    tiene = {dd.tipo for dd in docs if dd.estado in ("aceptado", "por_revisar")}
    return {"nombre": e.nombre, "puesto": e.puesto, "empresa": emp.nombre, "fecha_ingreso": e.fecha_ingreso.isoformat(),
            "vacaciones": rb.vacaciones(db, e),
            "avisos": [{"id": a.id, "titulo": a.titulo, "cuerpo": a.cuerpo, "fijado": a.fijado, "requiere_acuse": a.requiere_acuse,
                        "fecha": a.creado_en.isoformat(), "leido": a.id in leidos} for a in avisos],
            "solicitudes": [incidencia_dict(i) for i in inc],
            "recibos": [{"id": r.id, "inicio": p.inicio.isoformat(), "fin": p.fin.isoformat(), "fecha_pago": p.fecha_pago.isoformat(), "neto": str(r.neto)}
                        for r, p in recibos],
            "documentos": [documento_dict(dd) for dd in docs],
            "faltantes": [{"tipo": k, "texto": rb.DOCUMENTOS[k]} for k in rb.REQUERIDOS if k not in tiene],
            "tipos_solicitud": {k: rb.TIPOS[k] for k in rb.PIDE_EMPLEADO}, "tipos_documento": rb.DOCUMENTOS}


@router.post("/avisos/{aid}/acuse")
def acusar(aid: int, e: m.RhEmpleado = Depends(empleado_portal), db: Session = Depends(get_db)):
    if aid not in {a.id for a in rb.avisos_vigentes(db, e.organizacion_id, e.empresa_id)}:
        raise HTTPException(404, "Aviso no encontrado.")
    try:
        db.add(m.RhAcuse(aviso_id=aid, empleado_id=e.id))
        db.commit()
    except IntegrityError:
        db.rollback()
    return {"ok": True}


@router.post("/solicitudes", status_code=201)
async def solicitar(tipo: str = Form(...), desde: date = Form(...), hasta: date = Form(...), motivo: str | None = Form(None, max_length=500),
                    archivo: UploadFile | None = File(None), e: m.RhEmpleado = Depends(empleado_portal), db: Session = Depends(get_db)):
    if tipo not in rb.PIDE_EMPLEADO:
        raise HTTPException(422, "Ese tipo de solicitud no se puede pedir desde el portal.")
    dias = validar_incidencia(tipo, desde, hasta, None)
    if tipo == "vacaciones":
        v = rb.vacaciones(db, e)
        if Decimal(str(v["disponibles"])) - Decimal(str(v["pendientes_aprobar"])) < dias:
            raise HTTPException(422, f"Solo tiene {v['disponibles'] - v['pendientes_aprobar']:g} días disponibles en este periodo.")
    if tipo == "incapacidad" and (archivo is None or not archivo.filename):
        raise HTTPException(422, "Adjunte la incapacidad del IMSS (foto o PDF).")
    rel = nombre = None
    if archivo is not None and archivo.filename:
        try:
            rel, nombre = rb.guardar_archivo(e.organizacion_id, e.id, archivo.filename, await archivo.read(rb.MAX_ARCHIVO + 1))
        except ValueError as x:
            raise HTTPException(422, str(x))
    i = m.RhIncidencia(organizacion_id=e.organizacion_id, empleado_id=e.id, tipo=tipo, desde=desde, hasta=hasta, dias=dias,
                       motivo=(motivo or "").strip() or None, estado="pendiente", origen="portal", archivo=rel, archivo_nombre=nombre)
    db.add(i)
    db.add(m.Auditoria(organizacion_id=e.organizacion_id, accion="rh_solicitud_portal", entidad="rh_empleado", entidad_id=e.id, detalle={"tipo": tipo}))
    db.commit()
    return incidencia_dict(i)


@router.delete("/solicitudes/{iid}")
def cancelar(iid: int, e: m.RhEmpleado = Depends(empleado_portal), db: Session = Depends(get_db)):
    i = db.get(m.RhIncidencia, iid)
    if not i or i.empleado_id != e.id:
        raise HTTPException(404, "No encontrada.")
    if i.estado != "pendiente":
        raise HTTPException(409, "Solo puede cancelar solicitudes pendientes.")
    i.estado = "cancelada"
    db.commit()
    return incidencia_dict(i)


@router.get("/recibos/{rid}/pdf")
def recibo(rid: int, e: m.RhEmpleado = Depends(empleado_portal), db: Session = Depends(get_db)):
    r = db.get(m.RhRecibo, rid)
    p = db.get(m.RhPeriodo, r.periodo_id) if r else None
    if not r or r.empleado_id != e.id or p.estado != "cerrado":
        raise HTTPException(404, "Recibo no encontrado.")
    r.visto_en = r.visto_en or datetime.now(timezone.utc)
    db.commit()
    return Response(rb.recibo_pdf(r, e, db.get(m.RhEmpresa, p.empresa_id), p), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="recibo-{p.fin:%Y%m%d}.pdf"'})


@router.post("/documentos", status_code=201)
async def subir(tipo: str = Form(...), archivo: UploadFile = File(...), e: m.RhEmpleado = Depends(empleado_portal), db: Session = Depends(get_db)):
    if tipo not in rb.DOCUMENTOS or tipo in ("contrato", "alta_imss"):
        raise HTTPException(422, "Ese documento lo sube Recursos Humanos.")
    try:
        rel, nombre = rb.guardar_archivo(e.organizacion_id, e.id, archivo.filename or "", await archivo.read(rb.MAX_ARCHIVO + 1))
    except ValueError as x:
        raise HTTPException(422, str(x))
    dd = m.RhDocumento(organizacion_id=e.organizacion_id, empleado_id=e.id, tipo=tipo, archivo=rel, nombre=nombre, tamano=rb.ruta(rel).stat().st_size,
                       origen="portal", estado="por_revisar")
    db.add(dd)
    db.commit()
    return documento_dict(dd)


@router.get("/documentos/{did}")
def ver_documento(did: int, e: m.RhEmpleado = Depends(empleado_portal), db: Session = Depends(get_db)):
    dd = db.get(m.RhDocumento, did)
    if not dd or dd.empleado_id != e.id:
        raise HTTPException(404, "Documento no encontrado.")
    p = rb.ruta(dd.archivo)
    return FileResponse(p, media_type=rb.MIME.get(p.suffix, "application/octet-stream"), filename=dd.nombre)
