"""Seguimiento público de un trámite de escrituración (sin sesión: el token del enlace viaja en X-Enlace).

Qué ve quien tiene el enlace: el acto, el inmueble, el avance por etapas que la notaría marcó como visibles, la cita
de firma, el número de entrada al Registro y los documentos que le tocan entregar. NUNCA: notas internas, valor de la
operación, datos de contacto de las otras partes ni archivos. Puede SUBIR los documentos que se le piden."""
from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import auditar, ip_cliente
from ..freno import Ventana
from ..services import modulos
from ..services.escrituracion import base as eb
from ..services.evidencia import solicitudes as sol
from .escrituracion import guardar

router = APIRouter(prefix="/api/seguimiento", tags=["Nomira Escrituración — seguimiento público"])
_fallos_ip = Ventana(30, 900)
_subidas_ip = Ventana(40, 3600)


def _acceso(db: Session, request: Request, token: str | None) -> tuple[m.EsAcceso, m.EsExpediente]:
    ip = ip_cliente(request) or "?"
    if _fallos_ip.excedida(ip):
        raise HTTPException(429, "Demasiados intentos. Espere unos minutos.")
    a = db.scalar(select(m.EsAcceso).where(m.EsAcceso.token_hash == sol.huella(token))) if token and 20 <= len(token) <= 100 else None
    if a is None:
        _fallos_ip.registrar(ip)
        raise HTTPException(404, "El enlace no es válido. Pida uno nuevo a la notaría.")
    if a.revocado_en or sol._aware(a.expira_en) <= m.ahora():
        raise HTTPException(410, "Este enlace ya no está vigente. Pida uno nuevo a la notaría.")
    e = db.get(m.EsExpediente, a.expediente_id)
    org = db.get(m.Organizacion, a.organizacion_id)
    if not e or e.estado == "cancelado" or not org or org.estado != "activa" or "escrituracion" not in modulos.activos(db, a.organizacion_id):
        raise HTTPException(410, "Este enlace ya no está disponible.")
    return a, e


def _requisitos_visibles(db: Session, a: m.EsAcceso, e: m.EsExpediente) -> list[m.EsRequisito]:
    reqs = db.scalars(select(m.EsRequisito).where(m.EsRequisito.expediente_id == e.id, m.EsRequisito.estado != "no_aplica").order_by(m.EsRequisito.id)).all()
    if a.tipo in ("inmobiliaria", "otro"):
        return list(reqs)
    if a.tipo == "banco":
        return []
    p = db.get(m.EsParte, a.parte_id) if a.parte_id else None
    return [r for r in reqs if r.parte_id == a.parte_id or (r.parte_id is None and p and p.rol in eb.APORTA_INMUEBLE)]


def _puede_subir(a: m.EsAcceso) -> bool:
    return a.tipo in ("parte", "inmobiliaria")


@router.post("/estado")
def estado(request: Request, x_enlace: str | None = Header(None), db: Session = Depends(get_db)):
    a, e = _acceso(db, request, x_enlace)
    a.ultimo_acceso, a.visitas = m.ahora(), (a.visitas or 0) + 1
    org = db.get(m.Organizacion, e.organizacion_id)
    hitos = list(db.scalars(select(m.EsHito).where(m.EsHito.expediente_id == e.id).order_by(m.EsHito.orden)))
    visibles = [h for h in hitos if h.visible_cliente and h.estado != "no_aplica"]
    reg = next((h for h in hitos if h.clave == "registro" and h.estado == "hecho"), None)
    partes = {p.id: p for p in db.scalars(select(m.EsParte).where(m.EsParte.expediente_id == e.id))}
    reqs = _requisitos_visibles(db, a, e)
    responsable = db.get(m.Usuario, e.responsable_id) if e.responsable_id else None
    logo = None
    if org.logo_actualizado:
        datos = db.scalar(select(m.Organizacion.logo).where(m.Organizacion.id == org.id))
        if datos and len(datos) < 600_000:
            logo = "data:image/png;base64," + base64.b64encode(datos).decode()
    db.commit()
    return {
        "notaria": {"nombre": org.nombre, "logo": logo}, "para": a.nombre, "tipo": a.tipo,
        "folio": e.folio, "acto": eb.ACTOS.get(e.acto, e.acto), "titulo": e.titulo, "inmueble": e.inmueble, "estado": e.estado,
        "avance": eb.avance(hitos), "mensaje": e.mensaje_cliente,
        "etapas": [{"nombre": h.nombre, "estado": h.estado, "fecha": h.fecha.isoformat() if h.fecha else None, "nota": h.nota_publica} for h in visibles],
        "cita_firma": e.cita_firma.isoformat() if e.cita_firma else None, "cita_lugar": e.cita_lugar,
        "folio_registro": e.folio_registro if reg else None, "numero_escritura": e.numero_escritura if any(h.clave == "firma" and h.estado == "hecho" for h in hitos) else None,
        "responsable": responsable.nombre if responsable else None,
        "puede_subir": _puede_subir(a),
        "documentos": [{"id": r.id, "nombre": r.nombre, "de": partes[r.parte_id].nombre if r.parte_id in partes else "Inmueble / operación",
                        "estado": r.estado, "nota": r.nota if r.estado == "rechazado" else None, "obligatorio": r.obligatorio} for r in reqs],
    }


@router.post("/documentos", status_code=201)
async def subir(request: Request, archivo: UploadFile = File(...), requisito_id: int = Form(...), x_enlace: str | None = Header(None),
                db: Session = Depends(get_db)):
    a, e = _acceso(db, request, x_enlace)
    ip = ip_cliente(request) or "?"
    if _subidas_ip.excedida(ip):
        raise HTTPException(429, "Ha subido muchos archivos. Espere un momento.")
    if not _puede_subir(a):
        raise HTTPException(403, "Este enlace es solo de consulta.")
    r = db.get(m.EsRequisito, requisito_id)
    if not r or r.expediente_id != e.id or r.id not in {x.id for x in _requisitos_visibles(db, a, e)} or r.estado not in ("pendiente", "rechazado", "recibido"):
        raise HTTPException(404, "No encontrado.")
    contenido = await archivo.read(eb.MAX_ARCHIVO + 1)
    guardar(db, r, e, contenido, archivo.filename, "cliente")
    _subidas_ip.registrar(ip)
    auditar(db, None, "es_documento_cliente", "es_expediente", e.id, {"requisito": r.clave, "acceso": a.id}, request, organizacion_id=e.organizacion_id)
    db.commit()
    return {"ok": True, "mensaje": "Recibimos su documento. La notaría lo revisará."}
