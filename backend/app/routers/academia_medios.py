"""Medios de Academia que el navegador abre sin encabezado de sesión (etiqueta <video> e iframe de
SCORM) y verificación pública de diplomas.

- Videos y SCORM solo se sirven con una URL firmada, de corta duración, ligada a la persona y a la
  lección (la emite la vista de la lección, que sí exige sesión y acceso al curso).
- El contenido SCORM es de terceros: se sirve con CSP «sandbox», así que corre en un origen opaco y no
  puede leer la sesión de Nomira; se comunica con la página de Nomira solo por postMessage.
"""
from __future__ import annotations

import mimetypes
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import ip_cliente
from ..freno import Ventana
from ..services.academia import lms, scorm

router = APIRouter(tags=["Academia — medios y verificación"])
_verificar_ip = Ventana(30, 600)
CSP_SCORM = "sandbox allow-scripts allow-forms allow-popups allow-modals allow-downloads; default-src * data: blob: 'unsafe-inline' 'unsafe-eval'"
TIPOS = {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml",
         ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8", ".xml": "application/xml", ".mp4": "video/mp4",
         ".webm": "video/webm", ".mp3": "audio/mpeg", ".woff": "font/woff", ".woff2": "font/woff2", ".wasm": "application/wasm"}


def _leccion(db: Session, d: dict) -> m.AcLeccion:
    x = db.get(m.AcLeccion, d.get("l"))
    if not x or x.archivado_en:
        raise HTTPException(404, "No encontrado.")
    return x


@router.get("/api/academia-medios/video/{token}")
def video(token: str, db: Session = Depends(get_db)):
    d = lms.verificar(token, "video")
    x = _leccion(db, d)
    if not x.video_ruta or not os.path.isfile(x.video_ruta):
        raise HTTPException(404, "El video no está disponible.")
    tipo = {"mp4": "video/mp4", "m4v": "video/mp4", "webm": "video/webm", "mov": "video/quicktime"}.get(x.video_formato or "", "video/mp4")
    return FileResponse(x.video_ruta, media_type=tipo, headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff",
                                                                 "Content-Disposition": "inline"})


@router.get("/api/academia-medios/scorm/{token}/{ruta:path}")
def scorm_archivo(token: str, ruta: str, db: Session = Depends(get_db)):
    d = lms.verificar(token, "scorm")
    x = _leccion(db, d)
    if not x.scorm_dir:
        raise HTTPException(404, "No encontrado.")
    raiz = Path(x.scorm_dir).resolve()
    archivo = (raiz / ruta).resolve()
    if raiz not in archivo.parents or not archivo.is_file():
        raise HTTPException(404, "No encontrado.")
    ext = archivo.suffix.lower()
    cab = {"Content-Security-Policy": CSP_SCORM, "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
    if ext in (".html", ".htm"):
        u = db.get(m.Usuario, d.get("u"))
        al = db.scalar(select(m.AcAvanceLeccion).join(m.AcAvance, m.AcAvance.id == m.AcAvanceLeccion.avance_id)
                       .where(m.AcAvance.usuario_id == d.get("u"), m.AcAvanceLeccion.leccion_id == x.id))
        datos = scorm.datos_iniciales(al.scorm_datos if al else None, u.nombre if u else "", d.get("u"), x.scorm_version or "1.2")
        return Response(scorm.inyectar(archivo.read_bytes(), datos, x.scorm_version or "1.2"), media_type="text/html; charset=utf-8", headers=cab)
    tipo = TIPOS.get(ext) or mimetypes.guess_type(archivo.name)[0] or "application/octet-stream"
    return FileResponse(archivo, media_type=tipo, headers=cab)


@router.get("/api/academia-publico/verificar/{folio}")
def verificar(folio: str, request: Request, db: Session = Depends(get_db)):
    """Verificación pública de un diploma por su folio (el que aparece en el código QR). Muestra solo
    lo que ya está impreso en el diploma."""
    ip = ip_cliente(request) or "?"
    if _verificar_ip.excedida(ip):
        raise HTTPException(429, "Demasiadas consultas. Intente más tarde.")
    _verificar_ip.registrar(ip)
    folio = (folio or "").strip().upper()
    if len(folio) > 20:
        raise HTTPException(404, "No encontramos un diploma con ese folio.")
    a = db.scalar(select(m.AcAvance).where(m.AcAvance.constancia_folio == folio))
    if not a or not a.completado_en:
        raise HTTPException(404, "No encontramos un diploma con ese folio.")
    persona, org, c = db.get(m.Usuario, a.usuario_id), db.get(m.Organizacion, a.organizacion_id), db.get(m.AcCurso, a.curso_id)
    return {"valido": True, "folio": a.constancia_folio, "participante": persona.nombre if persona else "—", "curso": a.curso_titulo or (c.titulo if c else "—"),
            "organizacion": org.nombre if org else "—", "fecha": a.completado_en.isoformat(), "duracion_min": a.curso_duracion_min,
            "tipo": (c.reconocimiento if c else None) or "diploma"}
