"""Página pública de carga de documentos (sin cuenta). Solo permite SUBIR archivos al asunto del
enlace: ninguna ruta devuelve datos del expediente, ni nombres de otros documentos, hechos o notas.

El token llega en el encabezado X-Enlace (la página lo toma del fragmento de la URL), nunca en la
ruta, así que no queda en los registros de acceso. Tras verificar el código, la carga usa además una
sesión corta (X-Sesion) ligada a ese enlace.
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import ajustes
from ..db import get_db
from ..deps import auditar, ip_cliente
from ..freno import Ventana
from ..services import envios, modulos, plantillas_correo
from ..services.evidencia import solicitudes as sol
from .evidencia import EXT, _leer_archivo

router = APIRouter(prefix="/api/subida", tags=["Carga de documentos del cliente"])
log = logging.getLogger("nomira.subida")
_fallos_ip = Ventana(30, 900)  # enlaces o códigos inválidos por IP en 15 min
EXTENSIONES = {".pdf": "pdf", ".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp"}
NO_DISPONIBLE = "Este enlace ya no está disponible. Pida uno nuevo a su despacho."


def _ip(request: Request) -> str:
    return ip_cliente(request) or "?"


def _solicitud(db: Session, request: Request, token: str | None, *, bloquear: bool = False) -> m.EvSolicitud:
    ip = _ip(request)
    if _fallos_ip.excedida(ip):
        raise HTTPException(429, "Demasiados intentos. Espere unos minutos.")
    s = None
    if token and 20 <= len(token) <= 100:
        q = select(m.EvSolicitud).where(m.EvSolicitud.token_hash == sol.huella(token))
        s = db.scalar(q.with_for_update() if bloquear else q)
    if s is None:
        _fallos_ip.registrar(ip)
        raise HTTPException(404, "El enlace no es válido. Revise que lo haya copiado completo.")
    e = sol.estado(s)
    if e == "revocada":
        raise HTTPException(410, "El despacho canceló este enlace. Si aún necesita enviar documentos, pídale uno nuevo.")
    if e == "vencida":
        raise HTTPException(410, "Este enlace venció. Pida uno nuevo a su despacho.")
    org = db.get(m.Organizacion, s.organizacion_id)
    if not org or org.estado != "activa" or "evidencia" not in modulos.activos(db, s.organizacion_id):
        raise HTTPException(410, NO_DISPONIBLE)
    return s


def _info(db: Session, s: m.EvSolicitud, verificada: bool) -> dict:
    """Lo único que ve el cliente: quién le pide, qué le pide, hasta cuándo y el estado de LO QUE ÉL
    MISMO ENVIÓ con este enlace (nada más del asunto). El detalle de sus envíos solo tras verificar."""
    org = db.get(m.Organizacion, s.organizacion_id)
    autor = db.get(m.Usuario, s.creado_por_id) if s.creado_por_id else None
    ver = verificada or not s.requiere_codigo
    propios = db.scalars(select(m.EvDocumento).where(m.EvDocumento.solicitud_id == s.id).order_by(m.EvDocumento.id)).all() if ver else []
    pedidos = s.documentos or []
    estado_pedidos = [{"documento": x, "enviados": sum(1 for d in propios if d.solicitado_como == x)} for x in pedidos]
    envios = [{"nombre": d.nombre_original, "fecha": d.creado_en.isoformat(), "solicitado_como": d.solicitado_como,
               "estado": "Recibido, pendiente de revisión del despacho" if d.estado == "recibido" else "Recibido y revisado por el despacho"}
              for d in propios]
    return {"despacho": org.nombre, "solicita": autor.nombre if autor else None, "mensaje": s.mensaje,
            "documentos": pedidos, "estado_documentos": estado_pedidos, "mis_envios": envios,
            "expira_en": s.expira_en.isoformat(), "email": sol.enmascarar(s.email),
            "requiere_codigo": s.requiere_codigo, "verificado": verificada or not s.requiere_codigo,
            "estado": sol.estado(s), "archivos_enviados": s.archivos_recibidos,
            "archivos_restantes": max(s.max_archivos - s.archivos_recibidos, 0), "max_por_envio": sol.MAX_POR_ENVIO,
            "max_mb": ajustes().max_mb_archivo}


@router.post("/estado")
def estado(request: Request, x_enlace: str | None = Header(None), x_sesion: str | None = Header(None),
           db: Session = Depends(get_db)):
    s = _solicitud(db, request, x_enlace)
    ahora = m.ahora()
    if not s.primer_acceso_en or not s.ultimo_acceso_en or ahora - sol._aware(s.ultimo_acceso_en) > timedelta(minutes=30):
        auditar(db, None, "ev_solicitud_abierta", "ev_solicitud", s.id, {"asunto_id": s.asunto_id}, request,
                organizacion_id=s.organizacion_id)
    s.primer_acceso_en = s.primer_acceso_en or ahora
    s.ultimo_acceso_en = ahora
    db.commit()
    return _info(db, s, sol.sesion_valida(x_sesion, s))


@router.post("/codigo")
def enviar_codigo(request: Request, x_enlace: str | None = Header(None), db: Session = Depends(get_db)):
    s = _solicitud(db, request, x_enlace, bloquear=True)
    if not s.requiere_codigo:
        raise HTTPException(409, "Este enlace no necesita código.")
    if s.codigo_enviado_en and m.ahora() - sol._aware(s.codigo_enviado_en) < timedelta(seconds=sol.CODIGO_ESPERA_SEGUNDOS):
        raise HTTPException(429, "Ya le enviamos un código. Espere un minuto antes de pedir otro.")
    if s.codigos_enviados >= sol.CODIGOS_MAXIMOS:
        raise HTTPException(429, "Se pidieron demasiados códigos para este enlace. Pida uno nuevo a su despacho.")
    codigo = sol.nuevo_codigo()
    s.codigo_hash, s.codigo_expira_en = sol.huella_codigo(s.id, codigo), m.ahora() + timedelta(minutes=sol.CODIGO_MINUTOS)
    s.codigo_intentos, s.codigo_enviado_en, s.codigos_enviados = 0, m.ahora(), s.codigos_enviados + 1
    auditar(db, None, "ev_solicitud_codigo_enviado", "ev_solicitud", s.id, {"asunto_id": s.asunto_id}, request,
            organizacion_id=s.organizacion_id)
    db.commit()
    org = db.get(m.Organizacion, s.organizacion_id)
    asunto_c, html, texto = plantillas_correo.codigo_verificacion(org.nombre, codigo, sol.CODIGO_MINUTOS)
    r = envios.registrar_y_enviar(db, "ev_codigo", [s.email], asunto_c, html, texto, organizacion_id=s.organizacion_id)
    if r.estado != "enviado":
        raise HTTPException(503, "No pudimos enviar el código en este momento. Intente de nuevo en unos minutos.")
    return {"enviado": True, "email": sol.enmascarar(s.email), "minutos": sol.CODIGO_MINUTOS}


class Codigo(BaseModel):
    codigo: str = Field(min_length=4, max_length=12)


@router.post("/verificar")
def verificar(d: Codigo, request: Request, x_enlace: str | None = Header(None), db: Session = Depends(get_db)):
    s = _solicitud(db, request, x_enlace, bloquear=True)
    if not s.requiere_codigo:
        return {"sesion": sol.crear_sesion(s)}
    if not s.codigo_hash:
        raise HTTPException(409, "Primero pida su código.")
    if s.codigo_intentos >= sol.CODIGO_INTENTOS:
        raise HTTPException(429, "Demasiados intentos con este código. Pida uno nuevo.")
    if not sol.codigo_correcto(s, d.codigo):
        s.codigo_intentos += 1
        restantes = sol.CODIGO_INTENTOS - s.codigo_intentos
        if restantes <= 0:
            s.codigo_hash = None
        db.commit()
        _fallos_ip.registrar(_ip(request))
        raise HTTPException(422, "El código no es correcto o ya venció." + (f" Le quedan {restantes} intento(s)." if restantes > 0
                                                                              else " Pida uno nuevo."))
    s.codigo_hash = None  # un solo uso
    auditar(db, None, "ev_solicitud_verificada", "ev_solicitud", s.id, {"asunto_id": s.asunto_id}, request,
            organizacion_id=s.organizacion_id)
    db.commit()
    return {"sesion": sol.crear_sesion(s), "minutos": sol.SESION_MINUTOS}


@router.post("/archivos", status_code=201)
def subir(request: Request, archivos: list[UploadFile] = File(...), solicitado_como: list[str] = Form(default=[]),
          x_enlace: str | None = Header(None), x_sesion: str | None = Header(None), db: Session = Depends(get_db)):
    s = _solicitud(db, request, x_enlace, bloquear=True)
    if s.requiere_codigo and not sol.sesion_valida(x_sesion, s):
        raise HTTPException(401, "Su verificación venció. Pida un código nuevo para continuar.")
    if sol.estado(s) == "completa":
        raise HTTPException(409, "Ya se recibió el máximo de archivos para este enlace.")
    if len(archivos) > sol.MAX_POR_ENVIO:
        raise HTTPException(413, f"Envíe como máximo {sol.MAX_POR_ENVIO} archivos a la vez.")
    a = db.get(m.EvAsunto, s.asunto_id)
    res, nuevos = [], 0
    pedidos = set(s.documentos or [])
    for i, archivo in enumerate(archivos):
        como = (solicitado_como[i] if i < len(solicitado_como) else "").strip()
        como = como if como in pedidos else None  # solo se acepta un documento de la lista que pidió el despacho
        nombre = os.path.basename((archivo.filename or "documento").replace("\\", "/"))[:300] or "documento"
        if s.archivos_recibidos + nuevos >= s.max_archivos:
            res.append({"nombre": nombre, "aceptado": False, "motivo": "Se alcanzó el máximo de archivos para este enlace."})
            continue
        ext = os.path.splitext(nombre.lower())[1]
        if ext not in EXTENSIONES:
            res.append({"nombre": nombre, "aceptado": False, "motivo": "Solo se aceptan archivos PDF, JPG, PNG o WebP."})
            continue
        try:
            datos, formato = _leer_archivo(archivo)  # mismas reglas que la carga del despacho: tipo real, tamaño, páginas
        except HTTPException as e:
            res.append({"nombre": nombre, "aceptado": False, "motivo": e.detail})
            continue
        if EXTENSIONES[ext] != formato:
            res.append({"nombre": nombre, "aceptado": False, "motivo": "El contenido del archivo no coincide con su extensión."})
            continue
        sha = hashlib.sha256(datos).hexdigest()
        # Si ya existe en el asunto no se duplica, y al cliente no se le revela nada sobre lo que hay.
        if not db.scalar(select(m.EvDocumento.id).where(m.EvDocumento.asunto_id == a.id, m.EvDocumento.sha256 == sha)):
            carpeta = Path(ajustes().storage_dir) / str(a.organizacion_id) / "evidencia" / str(a.id)
            carpeta.mkdir(parents=True, exist_ok=True, mode=0o700)
            ruta = carpeta / f"{sha}.{EXT[formato]}"
            ruta.write_bytes(datos)
            os.chmod(ruta, 0o600)
            d = m.EvDocumento(organizacion_id=a.organizacion_id, asunto_id=a.id, nombre_original=nombre, sha256=sha,
                              tamano_bytes=len(datos), formato=formato, ruta=str(ruta), estado="recibido", origen="cliente",
                              solicitud_id=s.id, solicitado_como=como)
            db.add(d)
            db.flush()
            auditar(db, None, "ev_documento_recibido_cliente", "ev_documento", d.id,
                    {"asunto_id": a.id, "solicitud_id": s.id, "sha256": sha}, request, organizacion_id=a.organizacion_id)
            nuevos += 1
        res.append({"nombre": nombre, "aceptado": True})
    recibidos = sum(1 for r in res if r["aceptado"])
    if recibidos:
        s.archivos_recibidos += nuevos
        s.ultima_carga_en = m.ahora()
        a.actualizado_en = m.ahora()
    db.commit()
    if nuevos:
        _avisar_al_despacho(db, s, a, nuevos)
    return {"resultados": res, "recibidos": recibidos, "archivos_restantes": max(s.max_archivos - s.archivos_recibidos, 0)}


def _avisar_al_despacho(db: Session, s: m.EvSolicitud, a: m.EvAsunto, n: int) -> None:
    """Correo a quien creó la solicitud (y al responsable del asunto, si es otra persona)."""
    ids = {x for x in (s.creado_por_id, a.responsable_id) if x}
    usuarios = [u for u in (db.get(m.Usuario, i) for i in ids) if u and u.activo and not u.eliminado_en]
    url = ajustes().url_publica.rstrip("/") + f"/evidencia/{a.id}"
    for u in usuarios:
        asunto_c, html, texto = plantillas_correo.documentos_recibidos(u.nombre, a.nombre, n, s.email, url)
        envios.registrar_y_enviar(db, "ev_documentos_recibidos", [u.email], asunto_c, html, texto, organizacion_id=a.organizacion_id)
